"""GNSS Post Processing plugin for Agisoft Metashape

Copyright (C) 2021  Geoscan Ltd. https://www.geoscan.aero/

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

import re
from collections import deque
from datetime import datetime, timedelta
import os

from gnss_post_processing.app.utils.exceptions import NoEvents, InputDataError, NoEpochs
from gnss_post_processing.app.utils.antennas import get_antennas


def timer(func):
    def wrapper(*args, **kwargs):
        t1 = time.time()
        result = func(*args, **kwargs)
        print("{}: {} s".format(func.__name__, round(time.time() - t1, 3)))
        return result
    return wrapper


class RinexMeta:
    def __init__(self, data: (list, str)):
        self.header = list()
        self.time_start, self.time_end = None, None
        self.antenna_height = None
        self.antenna_type = None
        self.end_header_index = None

        if isinstance(data, list):
            self.source = data
            self.get_rinex_meta(rinex_data=data)
        elif isinstance(data, str):
            with open(data, 'r') as file:
                self.source = file.readlines()
            self.get_rinex_meta(rinex_data=self.source)
        else:
            raise ValueError

    def get_rinex_meta(self, rinex_data):
        for i, line in enumerate(rinex_data):
            self.header.append(line)
            data_line = line.split()

            time_start = self.get_start_time(data_line)
            self.time_start = time_start if time_start is not None else self.time_start
            time_end = self.get_end_time(data_line)
            self.time_end = time_end if time_end is not None else self.time_end

            antenna_height = self.get_antenna_height(data_line)
            self.antenna_height = antenna_height if antenna_height else self.antenna_height

            antenna_type = self.get_antenna_type(data_line)
            self.antenna_type = antenna_type if antenna_type else self.antenna_type

            if "END OF HEADER" in line:
                self.end_header_index = i
                break

        if self.time_start is None and self.time_end is None:
            raise InputDataError('No "TIME OF FIRST OBS" and "TIME OF LAST OBS" in RINEX.')

    def get_time_bounds_by_epochs(self):
        """If no time in header, use it"""

        def is_epoch(line):
            return RinexParser.is_timeline(line)[0] == 1

        index = self.end_header_index + 1
        while not is_epoch(self.source[index]):
            index += 1
        self.time_start = RinexParser.get_time_from_line(self.source[index])

        index = len(self.source) - 1
        while not is_epoch(self.source[index]):
            index -= 1
        self.time_end = RinexParser.get_time_from_line(self.source[index])

        return self.time_start, self.time_end

    @classmethod
    def get_start_time(cls, data_line: list):
        if data_line[-4:] == ['TIME', 'OF', 'FIRST', 'OBS']:
            if len(data_line[5].split('.')) > 1:
                microsecond = int(data_line[5].split('.')[1][:6])
            else:
                microsecond = 0

            time_start = datetime(year=int(data_line[0]), month=int(data_line[1]), day=int(data_line[2]),
                                  hour=int(data_line[3]), minute=int(data_line[4]),
                                  second=int(float(data_line[5])),
                                  microsecond=microsecond)
            return time_start
        else:
            return None

    @classmethod
    def get_end_time(cls, data_line: list):
        if data_line[-4:] == ['TIME', 'OF', 'LAST', 'OBS']:
            if len(data_line[5].split('.')) > 1:
                microsecond = int(data_line[5].split('.')[1][:6])
            else:
                microsecond = 0

            time_end = datetime(year=int(data_line[0]), month=int(data_line[1]), day=int(data_line[2]),
                                hour=int(data_line[3]), minute=int(data_line[4]),
                                second=int(float(data_line[5])),
                                microsecond=microsecond)
            return time_end
        else:
            return None

    @classmethod
    def get_antenna_height(cls, data_line: list):
        if data_line[-3:] == ['ANTENNA:', 'DELTA', 'H/E/N']:
            return float(data_line[0])
        else:
            return None

    @classmethod
    def get_antenna_type(cls, data_line: list):
        antennas = set(get_antennas())

        if data_line[-4:] == ['ANT', '#', '/', 'TYPE']:
            for item in data_line[:-4]:
                if item in antennas:
                    return item
        else:
            return None


class RinexParser:
    def __init__(self, obs_file, obs_frequency=0.1):
        self.obs_file = obs_file
        self.obs_frequency = obs_frequency

        self.rinex_data = self.open_rinex()
        self.meta = RinexMeta(data=self.rinex_data)
        self.epochs, self.events = None, None
        self.missed_events = list()

    def open_rinex(self):
        with open(self.obs_file, 'r') as file:
            return file.readlines()

    def make_obs_rinex(self, path: str, epochs_buffer: int = None):
        """
        :param path: str. Path to result RINEX file.
        :param epochs_buffer: int. Count of epochs to buffer event.
        """
        obs_rinex = list()
        epochs, events = self.get_epochs_and_events()
        epochs_d, events_d = {ep['time']: ep['data'] for ep in epochs}, {ev['time']: ev['data'] for ev in events}
        if epochs_buffer:
            storage = set()
            for ev_time, ev_data in events_d.items():
                nearest_epoch = ev_time.replace(microsecond=int(ev_time.microsecond / 100000) * 100000)
                for i in range(0, epochs_buffer):
                    time = nearest_epoch - timedelta(seconds=0.1*i)
                    if time in epochs_d:
                        storage.add(time)

                for i in range(1, epochs_buffer + 1):
                    time = nearest_epoch + timedelta(seconds=0.1 * i)
                    if time in epochs_d:
                        storage.add(time)

            events_stack = deque(events)
            event = events_stack.popleft() if events_stack else None
            for epoch_time in sorted(list(storage)):
                while event and event['time'] <= epoch_time:
                    obs_rinex.append(event['data'])
                    event = events_stack.popleft() if events_stack else None
                obs_rinex.extend(epochs_d[epoch_time])
        else:
            events = deque(events)
            event = events.popleft()
            for epoch in epochs:
                while event is not None and (epoch['time'] - event['time']) > timedelta(seconds=self.obs_frequency):
                    event = events.popleft() if len(events) > 0 else None
                    if event is not None:
                        self.missed_events.append(event)

                while event is not None and timedelta(0) < (epoch['time'] - event['time']) < timedelta(seconds=self.obs_frequency):
                    obs_rinex.append(event['data'])
                    event = events.popleft() if len(events) > 0 else None

                obs_rinex.extend(epoch['data'])

        self.__write_obs_file(path=path, data=obs_rinex)

    def get_epochs_and_events(self) -> (list, list):
        events, epochs = list(), list()
        i = self.meta.end_header_index + 1
        while i < len(self.rinex_data):
            event_status, digit_id = self.is_timeline(self.rinex_data[i])
            values = self.rinex_data[i].split()
            if event_status == 5:
                events.append({'time': self.get_time_from_line(values), 'data': self.rinex_data[i]})

            elif event_status == 1:
                epoch_time = self.get_time_from_line(values)
                epoch_data = list()

                epoch_data.append(self.rinex_data[i])
                while i < len(self.rinex_data) - 1 and self.get_time_from_line(self.rinex_data[i+1].split()) is None:
                    epoch_data.append(self.rinex_data[i+1])
                    i += 1
                epochs.append({'time': epoch_time, 'data': epoch_data})

            else:
                pass

            i += 1

        if events:
            events.sort(key=lambda event: event['time'])
        else:
            raise NoEvents("No events in rover rinex.")

        if not epochs:
            raise NoEpochs("No epochs in rover rinex")

        self.epochs, self.events = epochs, events

        return epochs, events

    @staticmethod
    def is_timeline(line) -> (int, int):
        """
        Method to identify time, event, epoch line.
        :param line: str
        :return: int. 1 - epoch, 5 - time event
        """
        try:
            v = line if isinstance(line, list) else line.split()
        except TypeError:
            return -1, -1

        idx = 0
        try:
            while not v[idx].isdigit():
                idx += 1
        except IndexError:
            return -1, -1

        try:
            year = len(v[idx]) in [2, 4]
            month = (1 <= int(v[idx+1]) <= 12)
            day = v[idx+2].isdigit() and 1 <= int(v[idx+2]) <= 31
            hour = v[idx+3].isdigit() and 0 <= int(v[idx+3]) <= 24
            minute = v[idx+4].isdigit() and 0 <= int(v[idx+4]) <= 59
            second = (0 <= float(v[idx+5]) < 60)

            # epoch flag OK. Epoch flags: 0 (OK), 1, 2, 3, 4, 5 (TIME EVENT), 6
            # more: https://kb.igs.org/hc/en-us/articles/115003980188-RINEX-2-11
            epoch_status = v[idx+6].isdigit() and int(v[idx+6]) == 0
            time_event = v[idx+6].isdigit() and int(v[idx+6]) == 5
        except (ValueError, IndexError):
            return -1, -1

        if all([year, month, day, hour, minute, second]):
            if epoch_status:
                return 1, idx
            elif time_event:
                return 5, idx
            else:
                return -1, -1
        else:
            return -1, -1

    @staticmethod
    def get_time_from_line(data_line: (str, list)) -> (None, datetime):
        """
        Check string line or splitted string from RINEX file if it is equal to string line with time information.
        If it is time, method returns datetime. Otherwise, method returns Nonetype object.
        """
        data_line = data_line if isinstance(data_line, list) else data_line.split()

        event_status, idx = RinexParser.is_timeline(data_line)
        if event_status > 0:
            if len(data_line[idx+5].split('.')) > 1:
                microsecond = int(data_line[idx+5].split('.')[1][:6])
            else:
                microsecond = 0

            year_value = data_line[idx] if len(data_line[idx]) == 4 else '20' + data_line[idx]  # rinex 3.x and 2.x
            timestamp = datetime(year=int(year_value),
                                 month=int(data_line[idx+1]), day=int(data_line[idx+2]),
                                 hour=int(data_line[idx+3]), minute=int(data_line[idx+4]),
                                 second=int(float(data_line[idx+5])),
                                 microsecond=microsecond)
            return timestamp
        else:
            return None

    def cut_rinex_by_time_bounds(self, path: str, start_time: datetime, end_time: datetime):
        obs_rinex = list()
        epochs, events = self.get_epochs_and_events()

        events = deque(events)
        event = events.popleft()
        for epoch in epochs:
            if epoch['time'] < start_time or epoch['time'] > end_time:
                continue

            if (epoch['time'] - event['time']) < timedelta(seconds=self.obs_frequency):
                obs_rinex.append(event['data'])
                event = events.popleft()

            obs_rinex.extend(epoch['data'])

        self.__write_obs_file(path=path, data=obs_rinex)

    def __write_obs_file(self, path, data: list):
        obs_file = self.meta.header
        obs_file.extend(data)
        with open(path, 'w') as file:
            file.writelines(obs_file)

    @staticmethod
    def get_antenna_height(path):
        """Extract antenna height cheaply"""

        with open(path, 'r') as file:
            i = 0
            while i < 250:
                line = file.readline()
                height = RinexMeta.get_antenna_height(line.split())
                if height:
                    return height

                if line.split() and "END OF HEADER" in line:
                    return None
                i += 1
        return None

    @staticmethod
    def get_antenna_type(path):
        """Extract antenna type cheaply"""

        with open(path, 'r') as file:
            i = 0
            while i < 250:
                line = file.readline()
                antenna_type = RinexMeta.get_antenna_type(line.split())
                if antenna_type:
                    return antenna_type

                if line.split() and "END OF HEADER" in line:
                    return None
                i += 1
        return None

    @staticmethod
    def get_start_end_times(path, identify_rover=False):
        rinex_time_start, rinex_time_end = None, None
        is_rover = False
        with open(path, 'r') as file:
            i = 0
            while i < 150:
                line = file.readline()
                data_line = line.split()

                time_start = RinexMeta.get_start_time(data_line)
                rinex_time_start = time_start if time_start else rinex_time_start

                time_end = RinexMeta.get_end_time(data_line)
                rinex_time_end = time_end if time_end else rinex_time_end

                if line.split() and "END OF HEADER" in line:
                    if identify_rover:
                        next_line = file.readline()
                        pattern = re.compile(r"2  \d\s$")
                        is_rover = re.search(pattern, next_line) is not None

                    break
                i += 1

            if rinex_time_start is None:
                while rinex_time_start is None:
                    line = file.readline()
                    rinex_time_start = RinexParser.get_time_from_line(line)
                    if rinex_time_start:
                        break

        while rinex_time_end is None:
            lines = read_end_file(path)
            for i in range(len(lines) - 1, -1, -1):
                rinex_time_end = RinexParser.get_time_from_line(lines[i].decode())
                if rinex_time_end:
                    break
            break

        return rinex_time_start, rinex_time_end, is_rover


def get_rinex_time_bounds(path):
    rinex_time_start, rinex_time_end = None, None
    with open(path, 'r') as file:
        i = 0
        while i < 150:
            line = file.readline()
            data_line = line.split()

            time_start = RinexMeta.get_start_time(data_line)
            rinex_time_start = time_start if time_start else rinex_time_start

            time_end = RinexMeta.get_end_time(data_line)
            rinex_time_end = time_end if time_end else rinex_time_end

            if rinex_time_start is not None and rinex_time_end is not None:
                break
            if line.split() and "END OF HEADER" in line:
                break
            i += 1

        if rinex_time_start is None:
            while rinex_time_start is None:
                line = file.readline()
                rinex_time_start = RinexParser.get_time_from_line(line)
                if rinex_time_start:
                    break

    while rinex_time_end is None:
        lines = read_end_file(path)
        for i in range(len(lines) - 1, -1, -1):
            rinex_time_end = RinexParser.get_time_from_line(lines[i].decode())
            if rinex_time_end:
                break
        break

    return rinex_time_start, rinex_time_end


def read_end_file(file) -> list:
    bfile = open(file, 'rb')
    bfile.seek(-10000, os.SEEK_END)
    lines = bfile.readlines()
    bfile.close()
    return lines


if __name__ == '__main__':
    pass
