import re

from wazuh_testing.modules import eps as eps
from wazuh_testing.tools import LOG_FILE_PATH, ANALYSISD_STATE
from wazuh_testing.tools.monitoring import FileMonitor, generate_monitoring_callback_groups


def make_analysisd_callback(pattern, prefix=eps.ANALYSISD_PREFIX):
    """Create a callback function from a text pattern.

    It already contains the analsisd prefix.

    Args:
        pattern (str): String to match on the log.
        prefix (str): regular expression used as a prefix before the pattern.

    Returns:
        lambda: function that returns if there's a match in the file

    Examples:
        >>> callback_bionic_update_started = make_vuln_callback("Starting Ubuntu Bionic database update")
    """
    pattern = r'\s+'.join(pattern.split())
    regex = re.compile(r'{}{}'.format(prefix, pattern))

    return lambda line: regex.match(line) is not None


def check_analysisd_event(file_monitor=None, callback='', error_message=None, update_position=True,
                          timeout=eps.T_60, prefix=eps.ANALYSISD_PREFIX, accum_results=1,
                          file_to_monitor=LOG_FILE_PATH):
    """Check if a analysisd event occurs

    Args:
        file_monitor (FileMonitor): FileMonitor object to monitor the file content.
        callback (str): log regex to check in Wazuh log
        error_message (str): error message to show in case of expected event does not occur
        update_position (boolean): filter configuration parameter to search in Wazuh log
        timeout (str): timeout to check the event in Wazuh log
        prefix (str): log pattern regex
        accum_results (int): Accumulation of matches.
    """
    file_monitor = FileMonitor(file_to_monitor) if file_monitor is None else file_monitor
    error_message = f"Could not find this event in {file_to_monitor}: {callback}" if error_message is None else \
        error_message

    file_monitor.start(timeout=timeout, update_position=update_position, accum_results=accum_results,
                       callback=make_analysisd_callback(callback, prefix), error_message=error_message)


def check_eps_disabled():
    """Check if the eps module is disabled"""
    check_analysisd_event(callback=fr'.*INFO: EPS limit disabled.*', timeout=eps.T_10)


def check_eps_enabled(maximum, timeframe):
    """Check if the eps module is enable"""
    check_analysisd_event(callback=fr".*INFO: EPS limit enabled, EPS: '{maximum}', timeframe: '{timeframe}'",
                          timeout=eps.T_10)


def check_configuration_error():
    """Check the configuration error event in ossec.log"""
    check_analysisd_event(timeout=eps.T_10, callback=r".* \(\d+\): Configuration error at.*",
                          error_message="Could not find the event 'Configuration error at 'etc/ossec.conf' "
                                        'in ossec.log', prefix=eps.MAILD_PREFIX)


def get_analysisd_state():
    """Get the states values of wazuh-analysisd.state file

    Returns:
        dict: Dictionary with all analysisd state
    """
    data = ""
    with open(ANALYSISD_STATE, 'r') as file:
        for line in file.readlines():
            if not line.startswith("#") and not line.startswith('\n'):
                data = data + line.replace('\'', '')
    data = data[:-1]
    analysisd_state = dict((a.strip(), b.strip()) for a, b in (element.split('=') for element in data.split('\n')))

    return analysisd_state


def get_messages_info(file_monitor, message, accum_results):
    """Check if the alerts.log file contains the message

    Args:
        file_monitor (FileMonitor): Wazuh log monitor
        message (str): Message to find
        accum_results (int): Total message to accumulate

    Returns:
        list: List with messages information
    """
    error_message = f"Could not find this event in {message}"

    result = file_monitor.start(timeout=eps.T_20, update_position=True, accum_results=accum_results,
                                callback=generate_monitoring_callback_groups(message),
                                error_message=error_message).result()

    return result
