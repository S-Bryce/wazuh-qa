'''
copyright: Copyright (C) 2015-2022, Wazuh Inc.

           Created by Wazuh, Inc. <info@wazuh.com>.

           This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

type: integration

brief: The 'wazuh-logcollector' daemon monitors configured files and commands for new log messages.
       Specifically, these tests will check if monitored commands that use several parameters are
       correctly executed by the logcollector, and the Wazuh API returns the same values for
       the configured 'localfile' section.
       Log data collection is the real-time process of making sense out of the records generated by
       servers or devices. This component can receive logs through text files or Windows event logs.
       It can also directly receive logs via remote syslog which is useful for firewalls and
       other such devices.

components:
    - logcollector

suite: configuration

targets:
    - agent
    - manager

daemons:
    - wazuh-logcollector
    - wazuh-apid

os_platform:
    - linux
    - windows

os_version:
    - Arch Linux
    - Amazon Linux 2
    - Amazon Linux 1
    - CentOS 8
    - CentOS 7
    - Debian Buster
    - Red Hat 8
    - Ubuntu Focal
    - Ubuntu Bionic
    - Windows 10
    - Windows Server 2019
    - Windows Server 2016

references:
    - https://documentation.wazuh.com/current/user-manual/capabilities/log-data-collection/index.html
    - https://documentation.wazuh.com/current/user-manual/reference/ossec-conf/localfile.html#command
    - https://documentation.wazuh.com/current/user-manual/reference/ossec-conf/localfile.html#alias
    - https://documentation.wazuh.com/current/user-manual/reference/ossec-conf/localfile.html#log-format

tags:
    - logcollector_configuration
'''
import os
import pytest
import sys
import wazuh_testing.api as api
from wazuh_testing.tools import get_service
import wazuh_testing.logcollector as logcollector
from wazuh_testing.tools.configuration import load_wazuh_configurations

# Marks
pytestmark = pytest.mark.tier(level=0)

# Configuration
no_restart_windows_after_configuration_set = True
test_data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
configurations_path = os.path.join(test_data_path, 'wazuh_basic_configuration.yaml')
wazuh_component = get_service()

local_internal_options = {'logcollector.remote_commands': '1', 'logcollector.debug': '2'}

parameters = [
    {'LOG_FORMAT': 'command', 'COMMAND': 'echo Testing'},
    {'LOG_FORMAT': 'command', 'COMMAND': 'df -P'},
    {'LOG_FORMAT': 'command', 'COMMAND': 'find / -type f -perm 4000'},
    {'LOG_FORMAT': 'command', 'COMMAND': 'ls /tmp/*'},
    {'LOG_FORMAT': 'command', 'COMMAND': '/tmp/script/my_script -a 1 -v 2 -b 3 -g 444 -k Testing'},
    {'LOG_FORMAT': 'full_command', 'COMMAND': 'echo Testing'},
    {'LOG_FORMAT': 'full_command', 'COMMAND': 'df -P'},
    {'LOG_FORMAT': 'full_command', 'COMMAND': 'find / -type f -perm 4000'},
    {'LOG_FORMAT': 'full_command', 'COMMAND': 'ls /tmp/*'},
    {'LOG_FORMAT': 'full_command', 'COMMAND': '/tmp/script/my_script -a 1 -v 2 -b 3 -g 444 -k Testing'}
]
metadata = [
    {'log_format': 'command', 'command': 'echo Testing'},
    {'log_format': 'command', 'command': 'df -P'},
    {'log_format': 'command', 'command': 'find / -type f -perm 4000'},
    {'log_format': 'command', 'command': 'ls /tmp/*'},
    {'log_format': 'command', 'command': '/tmp/script/my_script -a 1 -v 2 -b 3 -g 444 -k Testing'},
    {'log_format': 'full_command', 'command': 'echo Testing'},
    {'log_format': 'full_command', 'command': 'df -P'},
    {'log_format': 'full_command', 'command': 'find / -type f -perm 4000'},
    {'log_format': 'full_command', 'command': 'ls /tmp/*'},
    {'log_format': 'full_command', 'command': '/tmp/script/my_script -a 1 -v 2 -b 3 -g 444 -k Testing'},
]

configurations = load_wazuh_configurations(configurations_path, __name__,
                                           params=parameters,
                                           metadata=metadata)
configuration_ids = [f"{x['log_format']}_{x['command']}" for x in metadata]


# fixtures
@pytest.fixture(scope="module", params=configurations, ids=configuration_ids)
def get_configuration(request):
    """Get configurations from the module."""
    return request.param


@pytest.mark.filterwarnings('ignore::urllib3.exceptions.InsecureRequestWarning')
def test_configuration_command(configure_local_internal_options_module, get_configuration,
                               configure_environment, restart_logcollector):
    '''
    description: Check if the 'wazuh-logcollector' daemon can monitor commands that use multiple parameters.
                 For this purpose, the test will configure the logcollector to monitor a command, setting it
                 in the 'command' tag. Once the logcollector has started, it will check if the 'monitoring'
                 event, indicating that the command is being monitored, has been generated. Finally, the test
                 will verify that the Wazuh API returns the same values for the 'localfile' section that
                 the configured one.

    wazuh_min_version: 4.2.0

    tier: 0

    parameters:
        - get_local_internal_options:
            type: fixture
            brief: Get local internal options from the module.
        - configure_local_internal_options:
            type: fixture
            brief: Configure the Wazuh local internal options.
        - get_configuration:
            type: fixture
            brief: Get configurations from the module.
        - configure_environment:
            type: fixture
            brief: Configure a custom environment for testing.
        - restart_logcollector:
            type: fixture
            brief: Clear the 'ossec.log' file and start a new monitor.

    assertions:
        - Verify that the logcollector monitors the command specified in the 'command' tag.
        - Verify that the Wazuh API returns the same values for the 'localfile' section as the configured one.

    input_description: A configuration template (test_basic_configuration_location) is contained in an external
                       YAML file (wazuh_basic_configuration.yaml). That template is combined with different
                       test cases defined in the module. Those include configuration settings for
                       the 'wazuh-logcollector' daemon.

    expected_output:
        - r'INFO: Monitoring .* of command.*'

    tags:
        - logs
    '''
    cfg = get_configuration['metadata']

    log_callback = logcollector.callback_monitoring_command(cfg['log_format'], cfg['command'])
    wazuh_log_monitor.start(timeout=5, callback=log_callback,
                            error_message=logcollector.GENERIC_CALLBACK_ERROR_COMMAND_MONITORING)

    if wazuh_component == 'wazuh-manager':
        api.wait_until_api_ready()
        api.compare_config_api_response([cfg], 'localfile')
