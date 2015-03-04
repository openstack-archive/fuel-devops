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

ASSERTION_ERROR = AssertionError


def assert_equal(actual, expected, message=None):
    """Asserts that the two values are equal.

    :param actual: The actual value.
    :param expected: The expected value.
    :param message: A message to show in the event of a failure.
    """
    if actual == expected:
        return
    if not message:
        try:
            message = "%s != %s" % (actual, expected)
        except Exception:
            message = "The actual value did not equal the expected one."
    raise ASSERTION_ERROR(message)
