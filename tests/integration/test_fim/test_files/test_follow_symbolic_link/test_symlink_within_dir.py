# Copyright (C) 2015-2021, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

import os
from shutil import rmtree

import pytest
from wazuh_testing import global_parameters
from wazuh_testing.fim import SYMLINK, REGULAR, LOG_FILE_PATH, generate_params, create_file, \
    REQUIRED_ATTRIBUTES, CHECK_ALL, CHECK_SIZE, regular_file_cud
from wazuh_testing.tools import PREFIX
from wazuh_testing.tools.configuration import load_wazuh_configurations, check_apply_test
from wazuh_testing.tools.monitoring import FileMonitor

# Marks

pytestmark = [pytest.mark.linux, pytest.mark.sunos5, pytest.mark.darwin, pytest.mark.tier(level=1)]

# Variables

test_directories = [os.path.join(PREFIX, 'testdir')]
testdir = test_directories[0]
testdir_link = os.path.join(testdir, 'testdir_link')
testdir_target = os.path.join(PREFIX, 'testdir_target')
test_data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
configurations_path = os.path.join(test_data_path, 'wazuh_conf.yaml')
wazuh_log_monitor = FileMonitor(LOG_FILE_PATH)

# Configurations

conf_params, conf_metadata = generate_params(extra_params={'FOLLOW_MODE': 'yes'})
configurations = load_wazuh_configurations(configurations_path, __name__, params=conf_params, metadata=conf_metadata)


# Fixtures

@pytest.fixture(scope='module', params=configurations)
def get_configuration(request):
    """Get configurations from the module."""
    return request.param


# Functions

def extra_configuration_before_yield():
    """Create files and symlinks"""
    os.makedirs(testdir_target, exist_ok=True, mode=0o777)
    create_file(REGULAR, testdir_target, 'regular1')
    create_file(SYMLINK, testdir, 'testdir_link', target=testdir_target)


def extra_configuration_after_yield():
    """Remove symbolic link"""
    rmtree(testdir_target, ignore_errors=True)


# Tests

@pytest.mark.parametrize('tags_to_apply, checkers', [
    ({'symlink_within_directory'}, REQUIRED_ATTRIBUTES[CHECK_ALL] - {CHECK_SIZE}),
])
def test_symlink_within_dir(tags_to_apply, checkers, get_configuration, configure_environment, restart_syscheckd,
                            wait_for_fim_start):
    """Monitor a link within a monitored directory.

    The link configuration should prevail over the monitored directory (checks, follow_symbolic_link, etc...).

    Args:
      tags_to_apply (set): Run test if matches with a configuration identifier, skip otherwise.
      checkers (dict): Check options to be used.

    Raises:
        TimeoutError: If a expected event wasn't triggered.
        AttributeError: If a unexpected event was captured.
        ValueError: If the event's type and path are not the expected.
    """
    check_apply_test(tags_to_apply, get_configuration['tags'])
    scheduled = get_configuration['metadata']['fim_mode'] == 'scheduled'

    # Alerts from the pointed directory should have all checks except size
    regular_file_cud(testdir_target, wazuh_log_monitor, min_timeout=global_parameters.default_timeout, options=checkers,
                     time_travel=scheduled)
    # Alerts from the main directory should have all checks
    regular_file_cud(testdir, wazuh_log_monitor, min_timeout=global_parameters.default_timeout, time_travel=scheduled)
