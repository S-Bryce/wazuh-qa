# Copyright (C) 2015-2021, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2
import math
import os
import tempfile

import pytest

import wazuh_testing.logcollector as logcollector
from wazuh_testing import global_parameters
from wazuh_testing.tools import monitoring, file
from wazuh_testing.tools.services import control_service
from wazuh_testing.tools.configuration import load_wazuh_configurations
from wazuh_testing.tools.monitoring import LOG_COLLECTOR_DETECTOR_PREFIX

# Marks
pytestmark = [pytest.mark.linux, pytest.mark.darwin, pytest.mark.sunos5, pytest.mark.tier(level=0)]

# Configuration
DAEMON_NAME = "wazuh-logcollector"
test_data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
configurations_path = os.path.join(test_data_path, 'wazuh_only_future_events_conf.yaml')
temp_dir = tempfile.gettempdir()
log_test_path = os.path.join(temp_dir, 'test.log')
current_line = 0

local_internal_options = {
    'logcollector.debug': 2,
    'monitord.rotate_log': 0,
    'logcollector.vcheck_files': 5
}

parameters = [
    {'LOG_FORMAT': 'syslog', 'LOCATION': log_test_path, 'ONLY_FUTURE_EVENTS': 'no', 'MAX_SIZE': '10MB'},
    {'LOG_FORMAT': 'syslog', 'LOCATION': log_test_path, 'ONLY_FUTURE_EVENTS': 'yes', 'MAX_SIZE': '10MB'}
]
metadata = [
    {'log_format': 'syslog', 'location': log_test_path, 'only_future_events': 'no',
     'log_line': "Jan  1 00:00:00 localhost test[0]: line="},
    {'log_format': 'syslog', 'location': log_test_path, 'only_future_events': 'yes',
     'log_line': "Jan  1 00:00:00 localhost test[0]: line="}
]

configurations = load_wazuh_configurations(configurations_path, __name__, params=parameters, metadata=metadata)
configuration_ids = [f"rotate_{x['location']}_in_{x['log_format']}_format" for x in metadata]


def add_log_data(log_path, log_line_message, size_kib=1024, line_start=1):
    """
    Increase the space occupied by a log file by adding lines to it.

    In each line of the log, its number is added, so the final size of the log
    is always larger than the specified size.

    Args:
        log_path (str): Path to log file.
        log_line_message (str): Line content to be added to the log.
        size_kib (int, optional): Size in kibibytes (1024^2 bytes). Defaults to 1 MiB (1024 KiB).
        line_start (int, optional): Line number to start with. Defaults to 1.

    Returns:
        int: Last line number written.
    """
    if len(log_line_message):
        with open(log_path, 'a') as f:
            lines = math.ceil((size_kib * 1024) / len(log_line_message))
            for x in range(line_start, line_start + lines + 1):
                f.write(f"{log_line_message}{x}\n")
        return line_start + lines - 1
    return 0


# fixtures
@pytest.fixture(scope="module", params=configurations, ids=configuration_ids)
def get_configuration(request):
    """Get configurations from the module."""
    return request.param


@pytest.fixture(scope="module")
def get_local_internal_options():
    """Get internal configuration."""
    return local_internal_options


@pytest.fixture(scope="module")
def generate_log_file():
    """Generate a log of size greater than 10 MiB for testing."""
    global current_line
    file.write_file(log_test_path, '')
    current_line = add_log_data(log_test_path, metadata[0]['log_line'], size_kib=10240)
    yield
    file.remove_file(log_test_path)


def test_only_future_events(get_local_internal_options, configure_local_internal_options, get_configuration,
                            configure_environment, generate_log_file, restart_logcollector):
    """Check if the "only-future-events" option is working correctly.

    To do this, logcollector is stopped and several lines are added to a test log file.
    Depending on the value of the "only-future-events" option the following should happen:
    If the value is "yes" the added lines should not be detected, on the other hand,
    if the value is "no" those lines should be detected by logcollector.

    Args:
        get_local_internal_options (fixture): Get internal configuration.
        configure_local_internal_options (fixture): Set internal configuration for testing.
        get_configuration (fixture): Get configurations from the module.
        configure_environment (fixture): Configure a custom environment for testing.
        generate_log_file (fixture): Generate a log file for testing.
        restart_logcollector (fixture): Reset log file and start a new monitor.
    """
    config = get_configuration['metadata']
    global current_line

    # Ensure that the file is being analyzed
    message = fr"INFO: \(\d*\): Analyzing file: '{log_test_path}'."
    callback_message = monitoring.make_callback(pattern=message, prefix=LOG_COLLECTOR_DETECTOR_PREFIX)
    wazuh_log_monitor.start(timeout=global_parameters.default_timeout,
                            error_message=logcollector.GENERIC_CALLBACK_ERROR_COMMAND_MONITORING,
                            callback=callback_message)

    # Add one KiB of data to log
    current_line = add_log_data(config['location'], config['log_line'], 1, line_start=current_line + 1)

    message = f"DEBUG: Reading syslog message: '{config['log_line']}{current_line}'"
    callback_message = monitoring.make_callback(pattern=message, prefix=LOG_COLLECTOR_DETECTOR_PREFIX, escape=True)
    wazuh_log_monitor.start(timeout=global_parameters.default_timeout,
                            error_message=logcollector.GENERIC_CALLBACK_ERROR_COMMAND_MONITORING,
                            callback=callback_message)

    control_service('stop', daemon=DAEMON_NAME)

    # Add another KiB of data to log while logcollector is stopped
    first_line = current_line + 1
    current_line = add_log_data(config['location'], config['log_line'], 1, line_start=first_line)

    control_service('start', daemon=DAEMON_NAME)

    if config['only_future_events'] == 'no':
        # Logcollector should detect the first line written while it was stopped
        # Check first line
        message = f"DEBUG: Reading syslog message: '{config['log_line']}{first_line}'"
        callback_message = monitoring.make_callback(pattern=message, prefix=LOG_COLLECTOR_DETECTOR_PREFIX, escape=True)
        wazuh_log_monitor.start(timeout=global_parameters.default_timeout,
                                error_message=logcollector.GENERIC_CALLBACK_ERROR_COMMAND_MONITORING,
                                callback=callback_message)
        # Check last line
        message = f"DEBUG: Reading syslog message: '{config['log_line']}{current_line}'"
        callback_message = monitoring.make_callback(pattern=message, prefix=LOG_COLLECTOR_DETECTOR_PREFIX, escape=True)
        wazuh_log_monitor.start(timeout=global_parameters.default_timeout,
                                error_message=logcollector.GENERIC_CALLBACK_ERROR_COMMAND_MONITORING,
                                callback=callback_message)
    else:
        # Logcollector should NOT detect the log lines written while it was stopped
        with pytest.raises(TimeoutError):
            # Check first line
            message = f"DEBUG: Reading syslog message: '{config['log_line']}{first_line}'"
            callback_message = monitoring.make_callback(pattern=message, prefix=LOG_COLLECTOR_DETECTOR_PREFIX,
                                                        escape=True)
            wazuh_log_monitor.start(timeout=global_parameters.default_timeout,
                                    error_message=logcollector.GENERIC_CALLBACK_ERROR_COMMAND_MONITORING,
                                    callback=callback_message)
            # Check last line
            message = f"DEBUG: Reading syslog message: '{config['log_line']}{current_line}'"
            callback_message = monitoring.make_callback(pattern=message, prefix=LOG_COLLECTOR_DETECTOR_PREFIX,
                                                        escape=True)
            wazuh_log_monitor.start(timeout=global_parameters.default_timeout,
                                    error_message=logcollector.GENERIC_CALLBACK_ERROR_COMMAND_MONITORING,
                                    callback=callback_message)

    # Add another KiB of data to log (additional check)
    current_line = add_log_data(config['location'], config['log_line'], 1, line_start=current_line + 1)
    message = f"DEBUG: Reading syslog message: '{config['log_line']}{current_line}'"
    callback_message = monitoring.make_callback(pattern=message, prefix=LOG_COLLECTOR_DETECTOR_PREFIX, escape=True)
    wazuh_log_monitor.start(timeout=global_parameters.default_timeout,
                            error_message=logcollector.GENERIC_CALLBACK_ERROR_COMMAND_MONITORING,
                            callback=callback_message)