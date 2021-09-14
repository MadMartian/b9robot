#!/usr/bin/env python

import gi

gi.require_version('Gtk', '3.0')
gi.require_version('Vte', '2.91')

from gi.repository import Gtk, Gdk, Pango, Vte, GLib, GdkPixbuf
from signal import signal, SIGHUP
import traceback
import dbus
import festival
import yaml
import re
from enum import Enum
from typing import List, AnyStr
from dbus.mainloop.glib import DBusGMainLoop
from collections import namedtuple
from datetime import datetime
from time import strptime
import logging
import logging.config
from Xlib.display import Display, drawable
from Xlib.error import BadWindow, CatchError
from bs4 import BeautifulSoup
import cv2
from playsound import playsound

Message = namedtuple('Message', 'name summary body')
display = None


class Channel(Enum):
	LOG = 1
	DICTATION = 2
	VOID = 3


class TemplateReplacement:
	def __init__(self, match: AnyStr, replacement: AnyStr):
		self.match = re.compile(match, re.DOTALL | re.MULTILINE)
		self.replacement = replacement

	def apply(self, text: AnyStr):
		return self.match.sub(self.replacement, text)


class MatchDefinition:
	def __init__(self, name: AnyStr, summary: AnyStr, body: AnyStr):
		self.name = re.compile(name) if name else None
		self.summary = re.compile(summary, re.DOTALL | re.MULTILINE) if summary else None
		self.body = re.compile(body, re.DOTALL | re.MULTILINE) if body else None

	def matches(self, message: Message):
		return (self.name is None or self.name.match(message.name)) and (
				self.summary is None or self.summary.match(message.summary)) and (
				self.body is None or self.body.match(message.body))


class SoundEffect:
	def __init__(self, source: AnyStr, delay: float = 0):
		self.source = source
		self.delay = delay

	def play(self):
		playsound(self.source)

class Weekday(Enum):
	SUN = 0
	MON = 1
	TUE = 2
	WED = 3
	THU = 4
	FRI = 5
	SAT = 6


class Month(Enum):
	JAN = 1
	FEB = 2
	MAR = 3
	APR = 4
	MAY = 5
	JUN = 6
	JUL = 7
	AUG = 8
	SEP = 9
	OCT = 10
	NOV = 11
	DEC = 12


class Status(Enum):
	DISABLED = 0
	ENABLED = 1


class AbstractMatchDefinition:
	def __init__(self, status: Status):
		self.status = status

	def checkStatus(self, status: Status, fn):
		return self.status == status and fn(self)

	def enabled(self, fn):
		return self.checkStatus(Status.ENABLED, fn)

	def disabled(self, fn):
		return self.checkStatus(Status.DISABLED, fn)


class ScheduleDefinition(AbstractMatchDefinition):
	class Set:
		value = None

		def __init__(self, numericalizer):
			self.numericalizer = numericalizer

		def ranged(self, start, end):
			self.value = start, end

		def listed(self, list_value):
			self.value = list_value

		def in_range(self, value):
			if type(self.value) is tuple:
				start, end = self.value
			else:
				start = end = None

			x = self.numericalizer(value)

			return \
				self.value is None or (
					start is not None and end is not None and self.numericalizer(start) <= x <= self.numericalizer(end) or
					type(self.value) is list and x in map(self.numericalizer, self.value))

	def __init__ (self, status: Status):
		super().__init__(status)
		self.months = ScheduleDefinition.Set(lambda it: it.value)
		self.dates = ScheduleDefinition.Set(lambda it: it)
		self.days = ScheduleDefinition.Set(lambda it: it.value)
		self.times = ScheduleDefinition.Set(lambda time: time[0] * 60 + time[1])

	def matches(self, timestamp: datetime):
		return (
			self.months.in_range(Month(timestamp.month)) and
			self.dates.in_range(timestamp.day) and
			self.days.in_range(Weekday(timestamp.weekday())) and
			self.times.in_range((timestamp.hour, timestamp.minute))
		)


class WindowMatchDefinition(AbstractMatchDefinition):
	def __init__(self, status: Status):
		super().__init__(status)
		self.name = None
		self.clazz = None

	def set_name(self, name: AnyStr):
		self.name = re.compile(name)

	def set_class(self, clazz: AnyStr):
		self.clazz = re.compile(clazz)

	def matches(self, window: drawable.Window):
		name = window.get_wm_name()
		tuple = window.get_wm_class()
		(class1, class2) = tuple if tuple is not None else (None, None)
		return (self.name is None or (type(name) is str and self.name.match(name))) and (
				self.clazz is None or (
					type(class1) is str and self.clazz.match(class1)) or (
					type(class2) is str and self.clazz.match(class2)))

	def window_present(self, window: drawable.Window):
		try:
			if self.matches(window):
				return True
		except BadWindow as e:
			logging.error("Bad window encountered for definition (%s, %s)", self.name, self.clazz)
			return False

		children = window.query_tree().children
		for w in children:
			if self.window_present(w):
				return True

		return False

	def match(self):
		return self.window_present(display.screen().root)


class CapAvailabilityMap:
	def __init__(self):
		self.dict = dict()

	def get(self, index: int):
		existing = self.dict.get(index)
		if existing is None:
			cap = cv2.VideoCapture("/dev/video%d" % index)
			existing = cap is None or cap.isOpened()
			self.dict[index] = existing
			if cap.isOpened():
				cap.release()
				
		return existing

	def clear(self):
		self.dict.clear()


class VideoCapMatchDefinition(AbstractMatchDefinition):
	def __init__ (self, status: Status):
		super().__init__(status)
		self.available = False
		self.device = 0

	def set_device(self, device: int):
		self.device = device

	def set_available(self, available: bool):
		self.available = available

	def matches(self, device_map: CapAvailabilityMap):
		available = device_map.get(self.device)
		return available == self.available

	def enabled(self, device_map: CapAvailabilityMap):
		return self.checkStatus(Status.ENABLED, device_map)

	def disabled(self, device_map: CapAvailabilityMap):
		return self.checkStatus(Status.DISABLED, device_map)


class EndpointDefinition:
	def __init__(
			self,
			name: AnyStr = None,
			max_len: int = None,
			channels: List[Channel] = None,
			templates: List[TemplateReplacement] = None,
			match_definition: MatchDefinition = None,
			schedule: List[ScheduleDefinition] = None,
			windowing: List[WindowMatchDefinition] = None,
			camera: List[VideoCapMatchDefinition] = None,
			sound: SoundEffect = None):
		self.name = name
		self.max_len = max_len
		self.channels = channels
		self.templates = templates
		self.match_definition = match_definition
		self.schedule = schedule
		self.windowing = windowing
		self.camera = camera
		self.sound = sound

	def empty(self):
		return \
			self.name is None and self.channels is None and self.templates is None and self.match_definition is None and \
			self.schedule is None and self.windowing is None and self.camera is None and self.max_len is None


class ValidationError(Exception):
	def __init__(self, message):
		super().__init__(message)


class MatchSet:
	def __init__(self, definitions: List[AbstractMatchDefinition]):
		self.definitions = definitions
	
	def disabled_in(self, fn):
		return [it for it in self.definitions if it.disabled(fn)]

	def enabled_in(self, fn):
		return [it for it in self.definitions if it.enabled(fn)]
		
	def implicitly_enabled_in(self):
		return 0 == len(list(filter(lambda definition: definition.status == Status.ENABLED, self.definitions)))


class EndpointProcessor:
	default = EndpointDefinition()

	def __init__(self):
		self.endpoints_by_name = dict()
		self.unnamed_endpoints = list()
		self.camera_device_map = CapAvailabilityMap()

	def clear(self):
		self.default = EndpointDefinition()
		self.endpoints_by_name = dict()
		self.unnamed_endpoints = list()
		self.camera_device_map.clear()

	def add_endpoint(self, endpoint: EndpointDefinition):
		if endpoint.name is None:
			self.unnamed_endpoints.append(endpoint)
		elif endpoint.name in self.endpoints_by_name:
			self.endpoints_by_name[endpoint.name].append(endpoint)
		else:
			self.endpoints_by_name[endpoint.name] = [endpoint]

	def set_default(self, endpoint: EndpointDefinition):
		if not self.default.empty():
			raise ValidationError('Default endpoint already configured')
		else:
			self.default = endpoint

	def matches(self, match_definition: MatchDefinition, message: Message):
		chosen_match_definition = self.default.match_definition if not match_definition else match_definition
		return chosen_match_definition is None or chosen_match_definition.matches(message)

	def enabled(self, definitions: List[AbstractMatchDefinition], default: List[AbstractMatchDefinition], fn):
		all = MatchSet((default or []) + (definitions or []))
		chosen = MatchSet((default if not definitions else definitions) or [])
		return \
			chosen is None or \
			(chosen.enabled_in(fn) or chosen.implicitly_enabled_in()) and not all.disabled_in(fn)
	
	def scheduled(self, schedule: List[ScheduleDefinition], now: datetime):
		return self.enabled(schedule, self.default.schedule, lambda defn: defn.matches(now))

	def displayed(self, windowing: List[WindowMatchDefinition]):
		return self.enabled(windowing, self.default.windowing, lambda defn: defn.match())

	def cams(self, camera: List[VideoCapMatchDefinition], device_map: CapAvailabilityMap):
		return self.enabled(camera, self.default.camera, lambda defn: defn.matches(device_map))

	def apply_templates(self, templates: List[TemplateReplacement], text: AnyStr):
		for template in (self.default.templates or []) + (templates or []):
			text = template.apply(text)

		return text

	def dispatch(self, message: Message, now: datetime):
		processed = False
		named_endpoints = self.endpoints_by_name[message.name] if message.name in self.endpoints_by_name else []
		for endpoint in named_endpoints + self.unnamed_endpoints:
			processed = self.endpoint_dispatch(endpoint, message, now)
			if processed:
				break

		if not processed:
			self.endpoint_dispatch(self.default, message, now)

		self.camera_device_map.clear()

	def endpoint_dispatch(self, endpoint: EndpointDefinition, message: Message, now: datetime):
		try:
			if not self.matches(endpoint.match_definition, message):
				return False

			if not self.scheduled(endpoint.schedule, now) or not self.displayed(endpoint.windowing) \
				or not self.cams(endpoint.camera, self.camera_device_map):
				return True

			original_text = "%s :: %s" % (message.summary, message.body)
			plain = BeautifulSoup(original_text, "lxml")
			text = self.apply_templates(endpoint.templates, plain.text)
			sound = endpoint.sound
			if endpoint.max_len is not None:
				text = text[:endpoint.max_len]
			channels = self.default.channels if not endpoint.channels else endpoint.channels

			if Channel.LOG in channels:
				line = "Received notification via '%s' - %s" % (message.name, text) if text == original_text else \
					"Received and transformed notification via '%s' - %s (was '%s')" % (message.name, text, original_text)
				announce.info(line)

			if Channel.DICTATION in channels:
				if sound is not None:
					sound.play()
				festival.sayText(text)

			return True

		except BaseException as err:
			logging.error("Exception processing endpoint definition for %s - %s", endpoint.name, err)
			traceback.print_exc()
			return False


def dispatch_notification(bus, message):
	keys = ["app_name", "replaces_id", "app_icon", "summary", "body", "actions", "hints", "expire_timeout"]
	args = message.get_args_list()
	if len(args) == 8:
		notification = dict([(keys[i], args[i]) for i in range(8)])
		message = Message(
			name = notification['app_name'],
			summary = notification['summary'],
			body = notification['body']
		)
		processor.dispatch(message, datetime.now())


def load_configuration(target: EndpointProcessor):
	def load_schedule_element(schedule_element, set_component: ScheduleDefinition.Set, convert, kind: AnyStr):
		if type(schedule_element) is list:
			set_component.listed(list(map(convert, schedule_element)))
		if type(schedule_element) is str or type(schedule_element) is int:
			set_component.listed([ convert(schedule_element) ])
		elif 'from' in schedule_element and 'to' in schedule_element:
			set_component.ranged(convert(schedule_element['from']), convert(schedule_element['to']))
		else:
			raise ValidationError("Schedule in '%s' uses invalid %s syntax: %s" % (name, kind, schedule_element))

	def str_to_time_tuple(string: AnyStr):
		x = None
		time_formats = ['%I:%M', '%I%p', '%I:%M%p', '%I:%M %p']
		for format in time_formats:
			try:
				x = strptime(string, format)
				break
			except ValueError:
				pass

		if x is None:
			raise ValueError("Time format is not valid, require one of %s" % time_formats)

		return x.tm_hour, x.tm_min

	with open('/etc/b9robot/mappings.yaml') as f:
		docs = yaml.load_all(f)

		for doc in docs:
			name = doc.get('name')
			max_len = doc.get('max-length')
			channels = list(map(lambda it: Channel[it], doc['channels'])) if 'channels' in doc else []
			templates = []
			sound = None

			if 'match' in doc:
				matching = doc['match']
				match_definition = MatchDefinition(
					matching.get('name') or "^%s$" % doc['name'] if 'name' in doc else None,
					matching.get('summary'),
					matching.get('body')
				)
			else:
				match_definition = None

			if 'schedule' in doc:
				schedule = []
				for scheduling in doc['schedule']:
					definition = ScheduleDefinition(Status[scheduling['status']])
					if 'time' in scheduling:
						load_schedule_element(scheduling['time'], definition.times, str_to_time_tuple, 'time')

					if 'day' in scheduling:
						load_schedule_element(scheduling['day'], definition.days, lambda it: Weekday[it], 'day of week')

					if 'month' in scheduling:
						load_schedule_element(scheduling['month'], definition.months, lambda it: Month[it], 'month')

					if 'date' in scheduling:
						load_schedule_element(scheduling['date'], definition.dates, lambda it: it, 'date of month')

					schedule.append(definition)
			else:
				schedule = None

			if 'window' in doc:
				window = []
				for windowing in doc['window']:
					definition = WindowMatchDefinition(Status[windowing['status']])

					if 'name' in windowing:
						definition.set_name(windowing['name'])

					if 'class' in windowing:
						definition.set_class(windowing['class'])

					window.append(definition)
			else:
				window = None

			if 'camera' in doc:
				camera = []
				for cams in doc['camera']:
					definition = VideoCapMatchDefinition(Status[cams['status']])

					if 'device' in cams:
						definition.set_device(cams['device'])

					if 'available' in cams:
						definition.set_available(cams['available'])

					camera.append(definition)
			else:
				camera = None

			if 'templates' in doc:
				for elem in doc['templates']:
					templates.append(TemplateReplacement(elem['match'], elem['replace']))

			if 'sound' in doc:
				defn = doc['sound']
				sound = SoundEffect(source = defn['source'], delay = defn['delay'] if 'delay' in defn else None)
			else:
				sound = None

			endpoint = EndpointDefinition(name, max_len, channels, templates, match_definition, schedule, window, camera, sound)
			if 'match' in doc or 'name' in doc:
				target.add_endpoint(endpoint)
			else:
				target.set_default(endpoint)


def configure_logging():
	global announce
	logging.config.fileConfig(
		'/etc/b9robot/logging.conf',
		defaults = logging.basicConfig(
			format = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
		)
	)
	announce = logging.getLogger('announce')


def reload(sig, frame):
	logging.info("SIGHUP signal received, reloading configuration")
	try:
		processor.clear()
		configure_logging()
		load_configuration(processor)
		logging.info("Configurations reloaded successfully")
	except Exception as e:
		logging.exception("Failed to reload all configurations %s", e)


def init_display():
	global display
	display = Display()
	handler = CatchError(BadWindow)
	display.set_error_handler(handler)


processor = EndpointProcessor()
configure_logging()
load_configuration(processor)

signal(SIGHUP, reload)

loop = DBusGMainLoop(set_as_default = True)
session_bus = dbus.SessionBus()
session_bus.add_match_string(
    "type='method_call',interface='org.freedesktop.Notifications',member='Notify',eavesdrop=true")
session_bus.add_message_filter(dispatch_notification)

init_display()

GLib.MainLoop().run()
