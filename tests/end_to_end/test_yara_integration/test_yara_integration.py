import os
import json
import re
import pytest
from datetime import datetime
from tempfile import gettempdir

from wazuh_testing.tools.time import parse_date_time_format
from wazuh_testing import end_to_end as e2e
from wazuh_testing import event_monitor as evm
from wazuh_testing.tools import configuration as config

# Test cases data
test_data_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
test_cases_path = os.path.join(test_data_path, 'test_cases')
test_cases_file_path = os.path.join(test_cases_path, 'cases_yara_integration.yaml')
yara_script = os.path.join(test_data_path, 'configuration', 'yara.sh')
malware_downloader_script = os.path.join(test_data_path, 'configuration', 'malware_downloader.sh')
alerts_json = os.path.join(gettempdir(), 'alerts.json')

# Playbooks
configuration_playbooks = ['configuration.yaml']
events_playbooks = ['generate_events.yaml']
teardown_playbook = ['teardown.yaml']
configuration_extra_vars = {'yara_script': yara_script, 'malware_downloader_script': malware_downloader_script}

# Configuration
configurations, configuration_metadata, cases_ids = config.get_test_cases_data(test_cases_file_path)


@pytest.mark.parametrize('metadata', configuration_metadata, ids=cases_ids)
@pytest.mark.filterwarnings('ignore::urllib3.exceptions.InsecureRequestWarning')
def test_yara_integration(configure_environment, metadata, get_dashboard_credentials, generate_events,
                          clean_environment):
    rule_description = metadata['rule.description']
    rule_id = metadata['rule.id']
    rule_level = metadata['rule.level']
    data_yara_rule = metadata['extra']['data.yara_rule']
    timestamp_regex = r'\d+-\d+-\d+T\d+:\d+:\d+\.\d+[\+|-]\d+'

    expected_alert_json = fr".+timestamp\":\"({timestamp_regex})\",.+level\":{rule_level}.+description\"" \
                          fr":\"{rule_description}.+id.+{rule_id}"

    expected_indexed_alert = fr".+yara_rule\": \"{data_yara_rule}.+level.+{rule_level}.+id.+{rule_id}.+" \
                             fr"timestamp\": \"({timestamp_regex})\""

    query = e2e.make_query([
        {
          "term": {
            "rule.id": f"{rule_id}"
          }
        },
        {
          "term": {
            "rule.level": f"{rule_level}"
          }
        },
        {
          "term": {
            "data.yara_rule": f"{data_yara_rule}"
          }
        }
    ])

    # Check that alert has been raised and save timestamp
    raised_alert = evm.check_event(callback=expected_alert_json, file_to_monitor=alerts_json,
                                   error_message='The alert has not occurred').result()
    raised_alert_timestamp = raised_alert.group(1)
    raised_alert_timestamp = datetime.strptime(parse_date_time_format(raised_alert_timestamp), '%Y-%m-%d %H:%M:%S')

    # Get indexed alert
    response = e2e.get_alert_indexer_api(query=query, credentials=get_dashboard_credentials)
    indexed_alert = json.dumps(response.json())

    # Check that the alert data is the expected one
    alert_data = re.search(expected_indexed_alert, indexed_alert)
    assert alert_data is not None, 'Alert triggered, but not indexed'

    # Get indexed alert timestamp
    indexed_alert_timestamp = alert_data.group(1)
    indexed_alert_timestamp = datetime.strptime(parse_date_time_format(indexed_alert_timestamp), '%Y-%m-%d %H:%M:%S')

    # Check that alert has been indexed (checking that the timestamp is the expected one)
    assert indexed_alert_timestamp == raised_alert_timestamp, 'Alert triggered, but not indexed'
