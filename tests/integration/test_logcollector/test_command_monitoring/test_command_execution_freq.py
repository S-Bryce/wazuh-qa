'''
copyright: Copyright (C) 2015-2022, Wazuh Inc.

           Created by Wazuh, Inc. <info@wazuh.com>.

           This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

type: integration

brief: The 'wazuh-logcollector' daemon monitors configured files and commands for new log messages.
       Specifically, these tests will check if commands are executed at specific intervals set in
       the 'frequency' tag using the log formats 'command' and 'full_commnad'.
       Log data collection is the real-time process of making sense out of the records generated by
       servers or devices. This component can receive logs through text files or Windows event logs.
       It can also directly receive logs via remote syslog which is useful for firewalls and
       other such devices.

components:
    - logcollector

suite: command_monitoring

targets:
    - agent
    - manager

daemons:
    - wazuh-logcollector

os_platform:
    - linux
    - macos
    - solaris

os_version:
    - Arch Linux
    - Amazon Linux 2
    - Amazon Linux 1
    - CentOS 8
    - CentOS 7
    - Debian Buster
    - Red Hat 8
    - Solaris 10
    - Solaris 11
    - macOS Catalina
    - macOS Server
    - Ubuntu Focal
    - Ubuntu Bionic

references:
    - https://documentation.wazuh.com/current/user-manual/capabilities/log-data-collection/index.html
    - https://documentation.wazuh.com/current/user-manual/reference/ossec-conf/localfile.html#command
    - https://documentation.wazuh.com/current/user-manual/reference/ossec-conf/localfile.html#frequency

tags:
    - logcollector_cmd_exec
'''
import os
import pytest
from datetime import timedelta, datetime

from wazuh_testing import global_parameters, logger
from wazuh_testing.tools.time import TimeMachine
import wazuh_testing.logcollector as logcollector
from wazuh_testing.tools.configuration import load_wazuh_configurations

# Marks
pytestmark = [pytest.mark.tier(level=0)]

# Configuration
test_data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
configurations_path = os.path.join(test_data_path, 'wazuh_command_conf.yaml')

local_internal_options = {'logcollector.remote_commands': '1', 'logcollector.debug': '2', 'monitord.rotate_log': '0',
                          'windows.debug': '2'}


parameters = [
    {'LOG_FORMAT': 'command', 'COMMAND': 'echo command_5m', 'FREQUENCY': 300},  # 5 minutes.
    {'LOG_FORMAT': 'command', 'COMMAND': 'echo command_30m', 'FREQUENCY': 1800},  # 30 minutes.
    {'LOG_FORMAT': 'command', 'COMMAND': 'echo command_1h', 'FREQUENCY': 3600},  # 1 hour.
    {'LOG_FORMAT': 'command', 'COMMAND': 'echo command_24h', 'FREQUENCY': 86400},  # 24 hours.
    {'LOG_FORMAT': 'full_command', 'COMMAND': 'echo full_command_5m', 'FREQUENCY': 300},
    {'LOG_FORMAT': 'full_command', 'COMMAND': 'echo full_command_30m', 'FREQUENCY': 1800},
    {'LOG_FORMAT': 'full_command', 'COMMAND': 'echo full_command_1h', 'FREQUENCY': 3600},
    {'LOG_FORMAT': 'full_command', 'COMMAND': 'echo full_command_24h', 'FREQUENCY': 86400}
]
metadata = [
    {'log_format': 'command', 'command': 'echo command_5m', 'frequency': 300, 'freq_str': '5_minutes'},
    {'log_format': 'command', 'command': 'echo command_30m', 'frequency': 1800, 'freq_str': '30_minutes'},
    {'log_format': 'command', 'command': 'echo command_1h', 'frequency': 3600, 'freq_str': '1_hour'},
    {'log_format': 'command', 'command': 'echo command_24h', 'frequency': 86400, 'freq_str': '24_hours'},
    {'log_format': 'full_command', 'command': 'echo full_command_5m', 'frequency': 300, 'freq_str': '5_minutes'},
    {'log_format': 'full_command', 'command': 'echo full_command_30m', 'frequency': 1800, 'freq_str': '30_minutes'},
    {'log_format': 'full_command', 'command': 'echo full_command_1h', 'frequency': 3600, 'freq_str': '1_hour'},
    {'log_format': 'full_command', 'command': 'echo full_command_24h', 'frequency': 86400, 'freq_str': '24_hours'}
]

configurations = load_wazuh_configurations(configurations_path, __name__, params=parameters, metadata=metadata)
configuration_ids = [f"{x['log_format']}_{x['freq_str']}" for x in metadata]


# fixtures
@pytest.fixture(scope="module", params=configurations, ids=configuration_ids)
def get_configuration(request):
    """Get configurations from the module."""
    return request.param


def test_command_execution_freq(configure_local_internal_options_module, get_configuration, file_monitoring,
                                configure_environment, restart_monitord, restart_logcollector):
    '''
    description: Check if the 'wazuh-logcollector' daemon runs commands at the specified interval, set in
                 the 'frequency' tag. For this purpose, the test will configure the logcollector to run
                 a command at specific intervals. Then it will travel in time up to the middle of the interval
                 set in the 'frequency' tag, and verify that the 'running' event is not been generated. That
                 confirms that the command is not executed. Finally, the test will travel in time again up to
                 the next interval and verify that the command is executed by detecting the 'running' event.

    wazuh_min_version: 4.2.0

    tier: 0

    parameters:
        - configure_local_internal_options_module:
            type: fixture
            brief: Configure the Wazuh local internal options file.
        - get_configuration:
            type: fixture
            brief: Get configurations from the module.
        - file_monitoring:
            type: fixture
            brief: Handle the monitoring of a specified file.
        - configure_environment:
            type: fixture
            brief: Configure a custom environment for testing.
        - restart_monitord:
            type: fixture
            brief: Reset the log file and start a new monitor.
        - restart_logcollector:
            type: fixture
            brief: Clear the 'ossec.log' file and start a new monitor.

    assertions:
        - Verify that the logcollector runs commands at the interval set in the 'frequency' tag.
        - Verify that the logcollector does not run commands before the interval
          set in the 'frequency' tag expires.

    input_description: A configuration template (test_command_execution_freq) is contained in an external
                       YAML file (wazuh_command_conf.yaml), which includes configuration settings for
                       the 'wazuh-logcollector' daemon and, it is combined with the test cases
                       (log formats, frequencies, and commands to run) defined in the module.

    expected_output:
        - r'DEBUG: Running .*'

    tags:
        - logs
        - time_travel
    '''
    config = get_configuration['metadata']
    log_callback = logcollector.callback_running_command(log_format=config['log_format'], command=config['command'])

    seconds_to_travel = config['frequency'] / 2  # Middle of the command execution cycle.

    log_monitor.start(timeout=20, callback=log_callback,
                      error_message=logcollector.GENERIC_CALLBACK_ERROR_COMMAND_MONITORING)

    before = str(datetime.now())
    TimeMachine.travel_to_future(timedelta(seconds=seconds_to_travel))
    logger.debug(f"Changing the system clock from {before} to {datetime.now()}")

    # The command should not be executed in the middle of the command execution cycle.
    with pytest.raises(TimeoutError):
        log_monitor.start(timeout=global_parameters.default_timeout, callback=log_callback,
                          error_message=logcollector.GENERIC_CALLBACK_ERROR_COMMAND_MONITORING)

    before = str(datetime.now())
    TimeMachine.travel_to_future(timedelta(seconds=seconds_to_travel))
    logger.debug(f"Changing the system clock from {before} to {datetime.now()}")

    log_monitor.start(timeout=global_parameters.default_timeout, callback=log_callback,
                      error_message=logcollector.GENERIC_CALLBACK_ERROR_COMMAND_MONITORING)

    # Restore the system clock.
    TimeMachine.time_rollback()
