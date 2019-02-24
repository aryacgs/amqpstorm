"""AMQPStorm Connection.IO."""

import logging
import select
import socket
import threading
from errno import EAGAIN
from errno import EWOULDBLOCK

from amqpstorm import compatibility
from amqpstorm.base import MAX_FRAME_SIZE
from amqpstorm.compatibility import ssl
from amqpstorm.exception import AMQPConnectionError

EMPTY_BUFFER = bytes()
LOGGER = logging.getLogger(__name__)
POLL_TIMEOUT = 0.1


class Poller(object):
    """Simple Socket Poller implementation."""

    def __init__(self, fd):
        self.read = ((fd,), (), (), POLL_TIMEOUT)
        self.write = ((fd,), (fd,), (fd,), POLL_TIMEOUT)

    @property
    def ready_to_write(self):
        _, wlist, xlist = select.select(*self.write)
        if xlist:
            raise socket.error('connection/socket error')
        return wlist

    @property
    def ready_to_read(self):
        rlist, _, _ = select.select(*self.read)
        return rlist


class IO(object):
    """Internal Input/Output handler."""

    def __init__(self, parameters, exceptions=None, on_read_impl=None):
        self._exceptions = exceptions
        self._inbound_thread = None
        self._on_read_impl = on_read_impl
        self._running = threading.Event()
        self._parameters = parameters
        self.data_in = EMPTY_BUFFER
        self.poller = None
        self.socket = None
        self.use_ssl = self._parameters['ssl']

    def close(self):
        """Close Socket.

        :return:
        """
        self._running.clear()
        if self._inbound_thread:
            self._inbound_thread.join()
        if self.socket:
            self._close_socket()
        self._inbound_thread = None
        self.poller = None
        self.socket = None

    def open(self):
        """Open Socket and establish a connection.

        :raises AMQPConnectionError: Raises if the connection
                                     encountered an error.
        :return:
        """
        self.data_in = EMPTY_BUFFER
        self._running.set()
        sock_addresses = self._get_socket_addresses()
        self.socket = self._find_address_and_connect(sock_addresses)
        self.poller = Poller(self.socket)
        self._inbound_thread = self._create_inbound_thread()

    def write_to_socket(self, frame_data):
        """Write data to the socket.

        :param str frame_data:
        :return:
        """
        total_bytes_written = 0
        bytes_to_send = len(frame_data)
        while total_bytes_written < bytes_to_send:
            try:
                if not self.socket:
                    raise socket.error('connection/socket error')
                if not self.poller.ready_to_write:
                    continue
                bytes_written = (
                    self.socket.send(frame_data[total_bytes_written:])
                )
                if bytes_written == 0:
                    raise socket.error('connection/socket error')
                total_bytes_written += bytes_written
            except socket.timeout:
                pass
            except socket.error as why:
                if why.args[0] in (EWOULDBLOCK, EAGAIN):
                    continue
                self._exceptions.append(AMQPConnectionError(why))
                return

    def _close_socket(self):
        """Shutdown and close the Socket.

        :return:
        """
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()
        except (OSError, socket.error):
            pass

    def _get_socket_addresses(self):
        """Get Socket address information.

        :rtype: list
        """
        family = socket.AF_UNSPEC
        if not socket.has_ipv6:
            family = socket.AF_INET
        try:
            addresses = socket.getaddrinfo(self._parameters['hostname'],
                                           self._parameters['port'], family,
                                           socket.SOCK_STREAM)
        except socket.gaierror as why:
            raise AMQPConnectionError(why)
        return addresses

    def _find_address_and_connect(self, addresses):
        """Find and connect to the appropriate address.

        :param addresses:

        :raises AMQPConnectionError: Raises if the connection
                                     encountered an error.

        :rtype: socket.socket
        """
        for address in addresses:
            sock = self._create_socket(socket_family=address[0])
            try:
                sock.connect(address[4])
            except (IOError, OSError):
                continue
            return sock
        raise AMQPConnectionError(
            'Could not connect to %s:%d' % (
                self._parameters['hostname'], self._parameters['port']
            )
        )

    def _create_socket(self, socket_family):
        """Create Socket.

        :param int socket_family:
        :rtype: socket.socket
        """
        sock = socket.socket(socket_family, socket.SOCK_STREAM, 0)
        sock.settimeout(self._parameters['timeout'] or None)
        if self.use_ssl:
            if not compatibility.SSL_SUPPORTED:
                raise AMQPConnectionError(
                    'Python not compiled with support for TLSv1 or higher'
                )
            sock = self._ssl_wrap_socket(sock)
        return sock

    def _ssl_wrap_socket(self, sock):
        """Wrap SSLSocket around the Socket.

        :param socket.socket sock:
        :rtype: SSLSocket
        """
        if 'ssl_version' not in self._parameters['ssl_options']:
            self._parameters['ssl_options']['ssl_version'] = (
                compatibility.DEFAULT_SSL_VERSION
            )
        return ssl.wrap_socket(
            sock, do_handshake_on_connect=True,
            **self._parameters['ssl_options']
        )

    def _create_inbound_thread(self):
        """Internal Thread that handles all incoming traffic.

        :rtype: threading.Thread
        """
        inbound_thread = threading.Thread(target=self._process_incoming_data,
                                          name=__name__)
        inbound_thread.daemon = True
        inbound_thread.start()
        return inbound_thread

    def _process_incoming_data(self):
        """Retrieve and process any incoming data.

        :return:
        """
        while self._running.is_set():
            if self.poller.ready_to_read:
                self.data_in += self._receive()
                self.data_in = self._on_read_impl(self.data_in)

    def _receive(self):
        """Receive any incoming socket data.

            If an error is thrown, handle it and return an empty string.

        :return: data_in
        :rtype: bytes
        """
        data_in = EMPTY_BUFFER
        try:
            if not self.socket:
                raise socket.error('connection/socket error')
            return self.socket.recv(MAX_FRAME_SIZE)
        except socket.timeout:
            pass
        except (IOError, OSError) as why:
            if why.args[0] not in (EWOULDBLOCK, EAGAIN):
                self._exceptions.append(AMQPConnectionError(why))
                self._running.clear()
        return data_in
