#    Copyright 2013 - 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import functools
import time

from devops import logger
from devops import settings


def retry(count=10, delay=1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            i = 0
            while True:
                # noinspection PyBroadException
                try:
                    return func(*args, **kwargs)
                except Exception:
                    i += 1
                    if i >= count:
                        raise
                    time.sleep(delay)

        return wrapper

    return decorator


def revert_info(snapshot_name, description=""):
    logger.info("<" * 5 + "*" * 100 + ">" * 5)
    logger.info("{} Make snapshot: {}".format(description, snapshot_name))
    logger.info("You could revert this snapshot using [{command}]".format(
        command="dos.py revert {env} --snapshot-name {name} && "
        "dos.py resume {env} && virsh net-dumpxml {env}_admin | "
        "grep -P {pattern} -o "
        "| awk {awk_command}".format(
            env=settings.ENV_NAME,
            name=snapshot_name,
            pattern="\"(\d+\.){3}\"",
            awk_command="'{print \"Admin node IP: \"$0\"2\"}'"
        )
    )
    )

    logger.info("<" * 5 + "*" * 100 + ">" * 5)

