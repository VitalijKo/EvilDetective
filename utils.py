import hashlib
import zlib
import threading
import os
import re
import json
import uuid
import string
import tarfile
import tempfile
import logging
import functools
import contextlib
import datetime

logger = logging.getLogger(__name__)


def placebo(*args, **kwargs):
    def decorate(function):
        return function

    return decorate


def threaded(method):
    if os.environ.get('NOTHREAD'):
        return method

    @functools.wraps(method)
    def func(self, *args, **kwargs):
        def command():
            return method(self, *args, **kwargs)

        threading.Thread(target=command).start()

    return func


def human_time(sec):
    return f'{str(datetime.timedelta(seconds=sec)):0>8}'


def human_bytes(size):
    if size < 0:
        return human_bytes(0)

    powers = {20: 'KB', 30: 'MB', 40: 'GB', 50: 'TB', 60: 'PB'}

    if size < (2 ** 10):
        return f'{size}'

    for pw, name in powers.items():
        if size in range(2 ** pw):
            return f'{round(size / (2 ** (pw - 10)), pw // 20)}{name}'


def totupe(ver):
    res = re.match(r'^(?:\d\.?)+', ver.strip()).group()

    return tuple(map(int, res.split('.')))


def is_uuid(data):
    with contextlib.suppress(Exception):
        if isinstance(data, uuid.UUID):
            return data

        return uuid.UUID(data)

    return False


def is_hex(data):
    return all(c in string.hexdigits for c in data)


def get_koi(payload, keys):
    if payload and isinstance(payload, str):
        with contextlib.suppress(Exception):
            payload = re.sub('\n', '', payload)

            return get_koi(json.loads(payload), keys)

        return {}

    targets = [str, int, float, bool]

    result = dict.fromkeys(keys)

    def process(payload):
        if isinstance(payload, dict):
            for k, v in payload.items():
                if type(v) in targets:
                    if k in keys:
                        result[k] = v

                else:
                    process(v)

        elif isinstance(payload, list):
            for i in payload:
                process(i)

    if payload and isinstance(payload, (list, dict)):
        process(payload)

    return result if set(result.values()) else {}


def hash_file(file_path, algo='md5', buff=2**20):
    hasher = hashlib.new(algo)

    with open(f'{file_path}.{algo}', 'w') as W:
        with open(file_path, 'rb') as R:
            while True:
                d = R.read(buff)

                if not d:
                    break

                hasher.update(d)

        W.write(hasher.hexdigest())

    return hasher.hexdigest()


class DetectiveTools:
    AB_MAGIC = b'ANDROID BACKUP'

    @classmethod
    def ab_file_verify(cls, file_obj):
        if file_obj.read(len(cls.AB_MAGIC)) != cls.AB_MAGIC:
            raise DetectiveError('Not an Android backup file!')

        type_ = file_obj.read(4)

        if type_ == b'AES-':
            raise DetectiveError('AB file is encrypted.')

        elif type_ == b'none':
            pass

    @classmethod
    def ab_to_tar(cls, input_file, to_tmp=False, buffer=2**20):
        with open(input_file, 'rb') as backup_file:
            cls.ab_file_verify(backup_file)

            backup_file.seek(24)

            temptar = tempfile.NamedTemporaryFile(delete=False, suffix='.tar') if \
                to_tmp else open(f'{input_file}.tar', 'wb')

            zlib_obj = zlib.decompressobj()

            while True:
                d = backup_file.read(buffer)

                if not d:
                    break

                c = zlib_obj.decompress(d)

                temptar.write(c)

            zlib_obj.flush()

            temptar.close()

            return temptar.name

    @staticmethod
    def extract_form_tar(src_file, dst_dir, targets=None, full=False):
        if targets is None:
            targets = []

        with tarfile.open(src_file) as tar:
            for tar_name in tar.getnames():
                try:
                    tar.extract(tar_name, dst_dir)

                    logger.debug(tar_name)

                    if tar_name in targets or full:
                        yield tar_name
                except Exception as e:
                    logger.warning(f'Failed extracting: {tar_name} > {e}')

    @staticmethod
    def extract_tar_members(src_file, dst_dir, match='.+?'):
        rex = re.compile(match)

        with tarfile.open(src_file) as tar:
            for mem in tar.getmembers():
                if not rex.match(mem.path):
                    continue

                try:
                    tar.extract(mem, dst_dir)

                    yield mem
                except Exception as e:
                    logger.warning(f'Failed extracting: {mem} > {e}')


class DetectiveError(Exception):
    pass
