'''
copyright:
    Copyright (C) 2015-2021, Wazuh Inc.

    Created by Wazuh, Inc. <info@wazuh.com>.

    This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

type:
    integration

description:
    These tests will check if the `use_only_authd` setting of the API is working properly.
    This setting allows forcing the use of `authd` daemon when registering and removing agents.

tiers:
    - 0

component:
    manager

path:
    tests/integration/test_api/test_config/test_use_only_authd/

daemons:
    - authd
    - apid
    - analysisd
    - syscheckd
    - wazuh-db

os_support:
    - linux, centos 6
    - linux, centos 7
    - linux, centos 8
    - linux, rhel6
    - linux, rhel7
    - linux, rhel8
    - linux, amazon linux 1
    - linux, amazon linux 2
    - linux, debian buster
    - linux, debian stretch
    - linux, debian wheezy
    - linux, ubuntu bionic
    - linux, ubuntu xenial
    - linux, ubuntu trusty
    - linux, arch linux

coverage:

pytest_args:

tags:
    - api
'''
import os
import random
import time
from ipaddress import IPv4Address
from random import getrandbits
from secrets import token_hex

import pytest
import requests
from wazuh_testing.tools.configuration import check_apply_test, get_api_conf
from wazuh_testing.tools.services import control_service

# Marks

pytestmark = pytest.mark.server

# Configurations

test_data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
configurations_path = os.path.join(test_data_path, 'conf.yaml')
configuration = get_api_conf(configurations_path)


# Fixtures

@pytest.fixture(scope='module', params=configuration)
def get_configuration(request):
    """Get configurations from the module."""
    return request.param


# Functions

def extra_configuration_before_yield():
    control_service('stop', daemon='wazuh-authd')


def extra_configuration_after_yield():
    control_service('start', daemon='wazuh-authd')


# Tests

@pytest.mark.parametrize('tags_to_apply', [
    {'only_authd_enabled'},
    {'only_authd_disabled'},
])
def test_add_agent(tags_to_apply, get_configuration, configure_api_environment,
                   restart_api, wait_for_start, get_api_details):
    '''
    description:
        Check if `use_only_authd` forces the use of `authd` daemon when adding an agent.
        Verify that when `use_only_authd` option is enabled, if the `authd` daemon
        is not active, an error is returned.

    wazuh_min_version:
        3.13

    parameters:
        - tags_to_apply:
            type: set
            brief: Run test if match with a configuration identifier, skip otherwise.

        - get_configuration:
            type: fixture
            brief: Get configurations from the module.

        - configure_api_environment:
            type: fixture
            brief: Configure a custom environment for API testing.

        - restart_api:
            type: fixture
            brief: Reset `api.log` and start a new monitor.

        - wait_for_start:
            type: fixture
            brief: Wait until the API starts.

        - get_api_details:
            type: fixture
            brief: Get API information.

    assertions:
        - Verify that `status code` 400 (bad request) is received when the request to add the testing agent is made
          if the `use_only_authd` setting is enabled but the `authd` daemon is not active.
        - Verify that `status code` 200 (ok) is received when the request to add the testing agent is made
          if the `use_only_authd` setting is enabled and the `authd` daemon is active.
        - Verify that `status code` 200 (ok) is received when the request to delete the testing agent is made.

    test_input:
        A test case is contained in an external `YAML` file (conf.yaml)
        which includes API configuration parameters.

    logging:
        - api.log:
            - Requests made to the API should be logged.

    tags:

    '''
    check_apply_test(tags_to_apply, get_configuration['tags'])

    # API variables and random data for the request
    use_only_authd = get_configuration['configuration']['use_only_authd']
    api_details = get_api_details()
    api_details['base_url'] += '/agents'
    data = {'name': token_hex(16),
            'ip': IPv4Address(getrandbits(32)).compressed}

    if use_only_authd:
        control_service('stop', daemon='wazuh-authd')
    # Add agent POST request
    post_response = requests.post(api_details['base_url'], json=data, headers=api_details['auth_headers'], verify=False)

    # Assert if an error code was returned when wazuh-authd is disabled and use_only_authd enabled.
    if use_only_authd:
        assert post_response.status_code == 400, f'Expected status code was 400, but {post_response.status_code} was ' \
                                                 f'returned. \nFull response: {post_response.text}'
    else:
        assert post_response.status_code == 200, f'Expected status code was 200, but {post_response.status_code} was ' \
                                                 f'returned. \nFull response: {post_response.text}'

        # Delete the agent created
        agent_id = post_response.json()['data']['id']
        api_details['base_url'] += f"?agents_list={agent_id}&purge=true&status=&older_than=0s&status=all"
        delete_response = requests.delete(api_details['base_url'], headers=api_details['auth_headers'], verify=False)
        assert delete_response.status_code == 200, f'Delete response was not 200. Response: {delete_response.text}'


@pytest.mark.parametrize('tags_to_apply', [
    {'only_authd_enabled'},
    {'only_authd_disabled'},
])
def test_insert_agent(tags_to_apply, get_configuration, configure_api_environment,
                      restart_api, wait_for_start, get_api_details):
    '''
    description:
        Check if `use_only_authd` forces the use of `authd` daemon when inserting an agent.
        Verify that when `use_only_authd` option is enabled, if the `authd` daemon
        is not active, an error is returned.

    wazuh_min_version:
        3.13

    parameters:
        - tags_to_apply:
            type: set
            brief: Run test if match with a configuration identifier, skip otherwise.

        - get_configuration:
            type: fixture
            brief: Get configurations from the module.

        - configure_api_environment:
            type: fixture
            brief: Configure a custom environment for API testing.

        - restart_api:
            type: fixture
            brief: Reset `api.log` and start a new monitor.

        - wait_for_start:
            type: fixture
            brief: Wait until the API starts.

        - get_api_details:
            type: fixture
            brief: Get API information.

    assertions:
        - Verify that `status code` 400 (bad request) is received when the request to inserting the testing agent
          is made if the `use_only_authd` setting is enabled but the `authd` daemon is not active.
        - Verify that `status code` 200 (ok) is received when the request to quickly inserting the testing agent
          is made if the `use_only_authd` setting is enabled and the `authd` daemon is active.
        - Verify that `status code` 200 (ok) is received when the request to delete the testing agent is made.

    test_input:
        A test case is contained in an external `YAML` file (conf.yaml)
        which includes API configuration parameters.

    logging:
        - api.log:
            - Requests made to the API should be logged.

    tags:

    '''
    check_apply_test(tags_to_apply, get_configuration['tags'])

    # API variables and random data for the request
    use_only_authd = get_configuration['configuration']['use_only_authd']
    api_details = get_api_details()
    api_details['base_url'] += '/agents'
    data = {'name': token_hex(16),
            'ip': IPv4Address(getrandbits(32)).compressed,
            'id': str(random.randint(200, 999)),
            'key': token_hex(32)}

    # Insert agent POST request
    post_response = requests.post(api_details['base_url'] + '/insert', json=data, headers=api_details['auth_headers'],
                                  verify=False)

    # Assert if an error code was returned when wazuh-authd is disabled and use_only_authd enabled.
    if use_only_authd:
        assert post_response.status_code == 400, f'Expected status code was 400, but {post_response.status_code} was ' \
                                                 f'returned. \nFull response: {post_response.text}'
    else:
        assert post_response.status_code == 200, f'Expected status code was 200, but {post_response.status_code} was ' \
                                                 f'returned. \nFull response: {post_response.text}'

        # Delete the agent
        agent_id = post_response.json()['data']['id']
        api_details['base_url'] += f"?agents_list={agent_id}&purge=true&status=&older_than=0s&status=all"
        requests.delete(api_details['base_url'], headers=api_details['auth_headers'], verify=False)


@pytest.mark.parametrize('tags_to_apply', [
    {'only_authd_enabled'},
    {'only_authd_disabled'},
])
def test_insert_quick_agent(tags_to_apply, get_configuration, configure_api_environment,
                            restart_api, wait_for_start, get_api_details):
    '''
    description:
        Check if `use_only_authd` forces the use of `authd` daemon when quickly inserting an agent.
        Verify that when `use_only_authd` option is enabled, if the `authd` daemon
        is not active, an error is returned.

    wazuh_min_version:
        3.13

    parameters:
        - tags_to_apply:
            type: set
            brief: Run test if match with a configuration identifier, skip otherwise.

        - get_configuration:
            type: fixture
            brief: Get configurations from the module.

        - configure_api_environment:
            type: fixture
            brief: Configure a custom environment for API testing.

        - restart_api:
            type: fixture
            brief: Reset `api.log` and start a new monitor.

        - wait_for_start:
            type: fixture
            brief: Wait until the API starts.

        - get_api_details:
            type: fixture
            brief: Get API information.

    assertions:
        - Verify that `status code` 400 (bad request) is received when the request to quickly inserting
          the testing agent is made if the `use_only_authd` setting is enabled but the `authd` daemon is not active.
        - Verify that `status code` 200 (ok) is received when the request to quickly inserting
          the testing agent is made if the `use_only_authd` setting is enabled and the `authd` daemon is active.
        - Verify that `status code` 200 (ok) is received when the request to delete the testing agent is made.

    test_input:
        A test case is contained in an external `YAML` file (conf.yaml)
        which includes API configuration parameters.

    logging:
        - api.log:
            - Requests made to the API should be logged.

    tags:

    '''
    check_apply_test(tags_to_apply, get_configuration['tags'])

    # API variables
    use_only_authd = get_configuration['configuration']['use_only_authd']
    api_details = get_api_details()
    api_details['base_url'] += '/agents'

    # Quick insert agent POST request
    post_url = api_details['base_url'] + f'/insert/quick?agent_name={token_hex(16)}'
    post_response = requests.post(post_url, headers=api_details['auth_headers'], verify=False)

    # Assert if an error code was returned when wazuh-authd is disabled and use_only_authd enabled.
    if use_only_authd:
        assert post_response.status_code == 400, f'Expected status code was 400, but {post_response.status_code} was ' \
                                                 f'returned. \nFull response: {post_response.text}'
    else:
        assert post_response.status_code == 200, f'Expected status code was 200, but {post_response.status_code} was ' \
                                                 f'returned. \nFull response: {post_response.text}'

        # Delete the agent
        agent_id = post_response.json()['data']['id']
        api_details['base_url'] += f"?agents_list={agent_id}&purge=true&status=&older_than=0s&status=all"
        requests.delete(api_details['base_url'], headers=api_details['auth_headers'], verify=False)


@pytest.mark.parametrize('tags_to_apply', [
    {'only_authd_enabled'},
    {'only_authd_disabled'},
])
def test_delete_agent(tags_to_apply, get_configuration, configure_api_environment,
                      restart_api, wait_for_start, get_api_details):
    '''
    description:
        Check if `use_only_authd` forces the use of `authd` daemon when deleting an agent.
        Verify that when `use_only_authd` option is enabled, if the `authd` daemon
        is not active, an error is returned. In this test, `authd` daemon is activated
        in order to create an agent before it can be deleted.

    wazuh_min_version:
        3.13

    parameters:
        - tags_to_apply:
            type: set
            brief: Run test if match with a configuration identifier, skip otherwise.

        - get_configuration:
            type: fixture
            brief: Get configurations from the module.

        - configure_api_environment:
            type: fixture
            brief: Configure a custom environment for API testing.

        - restart_api:
            type: fixture
            brief: Reset `api.log` and start a new monitor.

        - wait_for_start:
            type: fixture
            brief: Wait until the API starts.

        - get_api_details:
            type: fixture
            brief: Get API information.

    assertions:
        - Verify that `status code` 200 (ok) is received when the request to insert the testing agent is made.
        - Verify the response received contains the field `total_affected_items` field set to 1
          when the request to delete the testing agent is made if the `use_only_authd` setting
          is disabled and the `authd` daemon is active.
        - Verify the response received contains the field `failed_items` with an error value of 1726
          when the request to delete the testing agent is made if the `use_only_authd` setting
          is enabled and the `authd` daemon is stopped.

    test_input:
        A test case is contained in an external `YAML` file (conf.yaml)
        which includes API configuration parameters.

    logging:
        - api.log:
            - Requests made to the API should be logged.

    tags:

    '''
    check_apply_test(tags_to_apply, get_configuration['tags'])
    use_only_authd = get_configuration['configuration']['use_only_authd']
    api_details = get_api_details()
    api_details['base_url'] += '/agents'

    if use_only_authd:
        control_service('start', daemon='wazuh-authd')
        time.sleep(1)

    # Create an agent to delete (we need wazuh-authd daemon running if use_only_authd in the configuration)
    post_url = api_details['base_url'] + f'/insert/quick?agent_name={token_hex(16)}'
    post_response = requests.post(post_url, headers=api_details['auth_headers'], verify=False)
    assert post_response.status_code == 200, 'Status code expected after quick inserting agent was 200.' \
                                             f' Full response: {post_response.text}'

    if use_only_authd:
        control_service('stop', daemon='wazuh-authd')
        time.sleep(1)

    # It is necessary to wait a bit after adding the agent before deleting or querying it.
    time.sleep(1)
    delete_url = api_details['base_url'] + \
        f"?agents_list={post_response.json()['data']['id']}&purge=true&status=&older_than=0s&status=all"
    delete_response = requests.delete(delete_url, headers=api_details['auth_headers'], verify=False).json()

    # Assert if an error code was returned when wazuh-authd is disabled and use_only_authd enabled.
    if not use_only_authd:
        assert delete_response['data']['total_affected_items'] == 1, 'Total_affected_items field expected to be 1.' \
                                                                     f'Full response: {delete_response}'
    else:
        assert delete_response['data']['failed_items'][0]['error']['code'] == 1726, 'Expected error code was 1726.' \
                                                                                    f'Full response: {delete_response}'
        # Delete created agent
        control_service('start', daemon='wazuh-authd')
        time.sleep(1)
        requests.delete(api_details['base_url'] + '?purge=true&status=&older_than=0s&status=all',
                        headers=api_details['auth_headers'], verify=False)
