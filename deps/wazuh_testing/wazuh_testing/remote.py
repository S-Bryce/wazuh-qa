# Copyright (C) 2015-2021, Wazuh Inc.
# Created by Wazuh, Inc. <info@wazuh.com>.
# This program is free software; you can redistribute it and/or modify it under the terms of GPLv2

import os
import socket

import wazuh_testing.tools.agent_simulator as ag

from wazuh_testing.tools import ARCHIVES_LOG_FILE_PATH
from wazuh_testing.tools import file
from wazuh_testing.tools import monitoring
from wazuh_testing.tools.services import control_service
from wazuh_testing.tools import QUEUE_SOCKETS_PATH

UDP = "UDP"
TCP = "TCP"
TCP_UDP = "TCP,UDP"
REMOTED_GLOBAL_TIMEOUT = 10
EXAMPLE_MESSAGE_EVENT = '1:/root/test.log:Feb 23 17:18:20 35-u20-manager4 sshd[40657]: Accepted publickey for root' \
                        ' from 192.168.0.5 port 48044 ssh2: RSA SHA256:IZT11YXRZoZfuGlj/K/t3tT8OdolV58hcCOJFZLIW2Y'
EXAMPLE_MESSAGE_PATTERN = 'Accepted publickey for root from 192.168.0.5 port 48044'
QUEUE_SOCKET_PATH = os.path.join(QUEUE_SOCKETS_PATH, 'queue')


def callback_detect_remoted_started(port, protocol, connection_type="secure"):
    """Creates a callback to detect if remoted was correctly started

    wazuh-remoted logs if it has correctly started for each connection type, the port and
    the protocol in the ossec.log

    Args:
        port (int): port configured for wazuh-remoted.
        protocol (str): protocol configured for wazuh-remoted. It can be UDP, TCP or both options at the same time.
        connection_type (str): it can be secure or syslog.

    Returns:
        callable: callback to detect this event
    """
    msg = fr"Started \(pid: \d+\). Listening on port {port}\/{protocol.upper()} \({connection_type}\)."

    return monitoring.make_callback(pattern=msg, prefix=monitoring.REMOTED_DETECTOR_PREFIX)


def callback_detect_syslog_event(message):
    """Creates a callback to detect the syslog messages in the archives.log

    Args:
        message (str): syslog message sent through the socket

    Returns:
        callable: callback to detect this event
    """
    expr = fr".*->\d+\.\d+\.\d+\.\d+\s{message}"
    return monitoring.make_callback(pattern=expr, prefix=None)


def send_syslog_message(message, port, protocol, manager_address="127.0.0.1"):
    """This function sends a message to the syslog server of wazuh-remoted

    Args:
        message (str): string to send as a syslog event.
        protocol (str): it can be UDP or TCP.
        port (int): port where the manager has bound the remoted port
        manager_address (str): address of the manager.

    Raises:
        ConnectionRefusedError: if there's a problem while sending messages to the manager
    """
    if protocol.upper() == UDP:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    if not message.endswith("\n"):
        message += "\n"

    sock.connect((manager_address, port))
    sock.send(message.encode())
    sock.close()


def create_archives_log_monitor():
    """Creates a FileMonitor for the archives.log file

    Returns:
        FileMonitor: object to monitor the archives.log
    """
    # Reset ossec.log and start a new monitor
    file.truncate_file(ARCHIVES_LOG_FILE_PATH)
    wazuh_archives_log_monitor = monitoring.FileMonitor(ARCHIVES_LOG_FILE_PATH)

    return wazuh_archives_log_monitor


def detect_archives_log_event(archives_monitor, callback, error_message, update_position=True, timeout=5):
    """Monitors the archives.log to detect a certain event

    Args:
        archives_monitor (FileMonitor): FileMonitor bound to the archives.log.
        callback (callable): lambda function used to detect the event.
        error_message (str): String used as human readable error if the event is not found.
        update_position (bool): bool value used to update the position of `archives_monitor`.
        timeout (int): maximum time in seconds to expect the event.

    Raises:
        TimeoutError: if the event is not found in the file.
    """
    archives_monitor.start(timeout=timeout, update_position=update_position, callback=callback,
                           error_message=error_message)


def check_syslog_event(wazuh_archives_log_monitor, message, port, protocol, timeout=10):
    """Check if a syslog event is properly received by the manager.

    Args:
        wazuh_archives_log_monitor (FileMonitor): FileMonitor object to monitor the archives.log.
        message (str): Message sent for syslog that must appear in the archives.log.
        protocol (str): it can be UDP or TCP.
        port (int): port where the manager has bound the remoted port.
        timeout (int): maximum time to expect the syslog event in the log file.
    """
    send_syslog_message(message, port, protocol)
    detect_archives_log_event(archives_monitor=wazuh_archives_log_monitor,
                              callback=callback_detect_syslog_event(message),
                              timeout=timeout,
                              error_message="Syslog message wasn't received or took too much time.")


def send_ping_pong_messages(protocol, manager_address, port):
    """This function sends the ping message to the manager

    This message is the first of many between the manager and the agents. It is used to check if both of them are ready
    to send and receive other messages

    Args:
        protocol (str): it can be UDP or TCP
        manager_address (str): address of the manager. IP and hostname are valid options
        port (int): port where the manager has bound the remoted port

    Returns:
        bytes: returns the #pong message from the manager

    Raises:
        ConnectionRefusedError: if there's a problem while sending messages to the manager
    """
    protocol = protocol.upper()
    if protocol == UDP:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ping_msg = b'#ping'
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        msg = '#ping'
        msg_size = len(bytearray(msg, 'utf-8'))
        # Since the message size's is represented as an unsigned int32, you need to use 4 bytes to represent it
        ping_msg = msg_size.to_bytes(4, 'little') + msg.encode()

    sock.connect((manager_address, port))
    sock.send(ping_msg)
    response = sock.recv(len(ping_msg))
    sock.close()
    return response if protocol == UDP else response[-5:]


def check_remoted_log_event(wazuh_log_monitor, callback_pattern, error_message='', update_position=False,
                            timeout=REMOTED_GLOBAL_TIMEOUT):
    """Allow to monitor the ossec.log file and search for a remoted event.

    Args:
        wazuh_log_monitor (FileMonitor): FileMonitor object to monitor the Wazuh log.
        callback_pattern (str): Regex pattern to search in ossec.log.
        error_message (str): Message error to show in case that the callback pattern is not found in the expected time.
        update_position (boolean): True to search from the last line of the log file, False to search in the complete
                                   log file.
        timeout (int): Maximum time in seconds for event search in log.

    Raises:
        TimeoutError: if callback pattern is not found in ossec.log in the expected time.
    """
    wazuh_log_monitor.start(
        timeout=timeout,
        update_position=update_position,
        callback=monitoring.make_callback(callback_pattern, monitoring.REMOTED_DETECTOR_PREFIX),
        error_message=error_message
    )


def check_tcp_connection_established_log(wazuh_log_monitor, update_position=False, ip_address='127.0.0.1'):
    """Allow to detect events of new incoming TCP connections in the ossec.log.

    Args:
        wazuh_log_monitor (FileMonitor): FileMonitor object to monitor the Wazuh log.
        update_position (boolean): True to search from the last line of the log file, False to search in the complete.
                                   log file.
        ip_address (str): IP address of incoming connection.

    Raises:
        TimeoutError: if callback pattern is not found in ossec.log in the expected time.
    """
    callback_pattern = f".*New TCP connection at {ip_address}.*"
    error_message = f"Could not find the log with the following pattern {callback_pattern}"

    check_remoted_log_event(wazuh_log_monitor, callback_pattern, error_message, update_position)


def wait_to_remoted_key_update(wazuh_log_monitor):
    """Allow to detect when remoted has updated its info with the client.keys

    This is necessary for remoted to correctly recognize the agent, and to be able to decrypt its messages.

    The reload time is editable in the internal_options.conf and defaults to 10 seconds.

    >> remoted.keyupdate_interval=10

    It is recommended to set this time to 5 or less for testing.

    Args:
        wazuh_log_monitor (FileMonitor): FileMonitor object to monitor the Wazuh log.

    Raises:
        TimeoutError: if could not find the remoted key loading log.
    """
    callback_pattern = '.*rem_keyupdate_main().*Checking for keys file changes.'
    error_message = 'Could not find the remoted key loading log'

    check_remoted_log_event(wazuh_log_monitor, callback_pattern, error_message, timeout=20)


def send_agent_event(wazuh_log_monitor, message=EXAMPLE_MESSAGE_EVENT, protocol=TCP, manager_address='127.0.0.1',
                     manager_port=1514, agent_os='debian7', agent_version='4.2.0', disable_all_modules=True):
    """Allow to create a new simulated agent and send a message to the manager.

    Args:
        wazuh_log_monitor (FileMonitor): FileMonitor object to monitor the Wazuh log.
        message (str): Raw event to send to the manager.
        protocol (str): it can be UDP or TCP.
        manager_address (str): Manager IP address.
        manager_port (str): Port used by remoted in the manager.
        agent_os (str): Agent operating system. The OS must belong to the agent simulator's list of allowed agents.
        agent_version (str): Agent version.
        disable_all_modules (boolean): True to disable all agent modules, False otherwise.

    Returns:
        tuple(Agent, Sender): agent and sender objects.
    """
    # Create an agent with agent simulator
    agent = ag.Agent(manager_address=manager_address, os=agent_os, version=agent_version,
                     disable_all_modules=disable_all_modules)

    # Wait until remoted has loaded the new agent key
    wait_to_remoted_key_update(wazuh_log_monitor)

    # Build the event message and send it to the manager as an agent event
    event = agent.create_event(message)

    # Send the event to the manager
    sender = ag.Sender(manager_address=manager_address, manager_port=manager_port, protocol=protocol)
    sender.send_event(event)

    return agent, sender


def check_queue_socket_event(raw_event=EXAMPLE_MESSAGE_PATTERN, timeout=30):
    """Allow searching for an expected event in the queue socket.

    Args:
        raw_event (str): Pattern regex to be found in the socket
        timeout (int): Maximum search time of the event in the socket. Default is 30 to allow enough time for the
                       other thread to send messages.

    Raises:
        TimeoutError: if could not find the pattern regex event in the queue socket.
    """
    # Do not delete. Function required for MITM to work
    def intercept_socket_data(data):
        return data

    error_message = 'Could not find the expected event in queue socket'
    callback = monitoring.make_callback(raw_event, '.*')

    # Stop analysisd daemon to free the socket. Important note: control_service(stop) deletes the daemon sockets.
    control_service('stop', daemon='wazuh-analysisd')

    # Create queue socket if it does not exist.
    file.bind_unix_socket(QUEUE_SOCKET_PATH, UDP)

    # Intercept queue sockets events
    mitm = monitoring.ManInTheMiddle(address=QUEUE_SOCKET_PATH, family='AF_UNIX', connection_protocol=UDP,
                                     func=intercept_socket_data)
    mitm.start()

    # Monitor MITM queue
    socket_monitor = monitoring.QueueMonitor(mitm.queue)

    try:
        # Start socket monitoring
        socket_monitor.start(timeout=timeout, callback=callback, error_message=error_message, update_position=False)
    finally:
        mitm.shutdown()
        control_service('start', daemon='wazuh-analysisd')