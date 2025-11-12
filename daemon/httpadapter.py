#
# Copyright (C) 2025 pdnguyen of HCMC University of Technology VNU-HCM.
# All rights reserved.
# This file is part of the CO3093/CO3094 course.
#
# WeApRous release
#

"""
daemon.httpadapter
~~~~~~~~~~~~~~~~~

This module provides a http adapter object to manage and persist 
http settings (headers, bodies). The adapter supports both
raw URL paths and RESTful route definitions, and integrates with
Request and Response objects to handle client-server communication.
"""

from urllib import request
from .request import Request
from .response import Response
from .dictionary import CaseInsensitiveDict
import json

class HttpAdapter:
    """
    A mutable :class:`HTTP adapter <HTTP adapter>` for managing client connections
    and routing requests.

    The `HttpAdapter` class encapsulates the logic for receiving HTTP requests,
    dispatching them to appropriate route handlers, and constructing responses.
    It supports RESTful routing via hooks and integrates with :class:`Request <Request>` 
    and :class:`Response <Response>` objects for full request lifecycle management.

    Attributes:
        ip (str): IP address of the client.
        port (int): Port number of the client.
        conn (socket): Active socket connection.
        connaddr (tuple): Address of the connected client.
        routes (dict): Mapping of route paths to handler functions.
        request (Request): Request object for parsing incoming data.
        response (Response): Response object for building and sending replies.
    """

    __attrs__ = [
        "ip",
        "port",
        "conn",
        "connaddr",
        "routes",
        "request",
        "response",
    ]

    def __init__(self, ip, port, conn, connaddr, routes):
        """
        Initialize a new HttpAdapter instance.

        :param ip (str): IP address of the client.
        :param port (int): Port number of the client.
        :param conn (socket): Active socket connection.
        :param connaddr (tuple): Address of the connected client.
        :param routes (dict): Mapping of route paths to handler functions.
        """

        #: IP address.
        self.ip = ip
        #: Port.
        self.port = port
        #: Connection
        self.conn = conn
        #: Conndection address
        self.connaddr = connaddr
        #: Routes
        self.routes = routes
        #: Request
        self.request = Request()
        #: Response
        self.response = Response(port=port)

    def handle_client(self, conn, addr, routes):
        """
        Handle an incoming client connection.

        This method reads the request from the socket, prepares the request object,
        invokes the appropriate route handler if available, builds the response,
        and sends it back to the client.

        :param conn (socket): The client socket connection.
        :param addr (tuple): The client's address.
        :param routes (dict): The route mapping for dispatching requests.
        """

        # Connection handler.
        self.conn = conn        
        # Connection address.
        self.connaddr = addr
        # Request handler
        req = self.request
        # Response handler
        resp = self.response

        # Handle the request
        msg = conn.recv(1024).decode()
        req.prepare(msg, routes)

        # Handle request hook
        if self.port != 9000 and req.method == 'POST' and req.path == '/login':
            body_params = {}
            if req.body:
                pairs = req.body.split('&')
                for pair in pairs:
                    key, val = pair.split('=', 1)
                    body_params[key.strip()] = val.strip()
            if body_params.get('username') == 'admin' and body_params.get('password') == 'password':
                resp.status_code = 302
                resp.headers['Set-Cookie'] = 'auth=true'
                resp.headers["Location"] = "/index.html"
                req.path='/index.html'
                resp.authenticated = True
            else:
                resp.status_code = 401
                resp.reason = 'Unauthorized'
                resp._content = (
                    b"<html><head><title>401 Unauthorized</title></head>"
                    b"<body><h1>401 Unauthorized</h1><p>Invalid username or password.</p></body></html>"
                )
                header = (
                    "HTTP/1.1 401 Unauthorized\r\n"
                    "Content-Type: text/html\r\n"
                    f"Content-Length: {len(resp._content)}\r\n"
                    "Connection: close\r\n\r\n"
                ).encode("utf-8")
                conn.sendall(header + resp._content)
                conn.close()
                return 

        elif req.method == 'GET':
            cookies_string = req.headers.get('cookie', '')

            # ============ FIX: ADD API ENDPOINTS TO PUBLIC PATHS ============
            # Cho phép truy cập API endpoints và static files không cần auth
            public_paths = (
                "/login.html", 
                "/css/", 
                "/js/", 
                "/images/", 
                "/static/",
                # API endpoints cho tracker
                "/submit-info",
                "/get-list",
                "/connect-peer",
                "/broadcast-peer",
                "/send-peer"
            )
            
            if req.path.startswith(public_paths) or req.path in public_paths:
                resp.status_code = 200
                resp.reason = "OK"
                resp.authenticated = True  # Mark as authenticated to skip further checks

            # Nếu có cookie auth thì cho vào index
            elif self.port == 9000 and 'auth=true' in cookies_string:
                if req.path == '/':
                    req.path = '/index.html'
                resp.status_code = 200
                resp.reason = "OK"

            # Còn lại thì bắt redirect về login
            elif self.port != 9000:
                req.path = "/login.html"
                resp.status_code = 302
                resp.reason = "Redirect to login"
                resp.headers["Location"] = "/login.html"
            
            elif self.port == 9000:
                if req.path == '/':
                    req.path = '/index.html'
                resp.status_code = 200
                resp.reason = "OK"
                resp.authenticated = True

        # ============ FIX: HANDLE POST REQUESTS FOR API ============
        elif req.method == 'POST':
            # Bypass authentication for API endpoints
            api_endpoints = ["/submit-info", "/connect-peer", "/broadcast-peer", "/send-peer"]
            if req.path in api_endpoints:
                resp.status_code = 200
                resp.reason = "OK"
                resp.authenticated = True


        if req.hook:
            print("[HttpAdapter] hook in route-path METHOD {} PATH {}".format(req.hook._route_path,req.hook._route_methods))
            
            # ============ FIX: PROPERLY HANDLE HOOK RETURN VALUES ============
            result = req.hook(headers=req.headers, body=req.body)
            
            # Handle tuple return (body, content_type) or (body, content_type, status_code)
            if isinstance(result, tuple):
                if len(result) == 2:
                    body, content_type = result
                    resp._content = body.encode('utf-8') if isinstance(body, str) else body
                    resp.headers["Content-Type"] = content_type
                    resp.status_code = 200
                elif len(result) == 3:
                    body, content_type, status_code = result
                    resp._content = body.encode('utf-8') if isinstance(body, str) else body
                    resp.headers["Content-Type"] = content_type
                    resp.status_code = status_code
            # Handle dict return
            elif isinstance(result, dict):
                resp._content = json.dumps(result).encode('utf-8')
                resp.headers["Content-Type"] = "application/json"
                resp.status_code = 200
            # Handle string return
            elif isinstance(result, str):
                resp._content = result.encode('utf-8')
                resp.status_code = 200
            # Handle bytes return
            elif isinstance(result, bytes):
                resp._content = result
                resp.status_code = 200

            header_bytes = resp.build_response_header(req)
            conn.sendall(header_bytes + resp._content)
            conn.close()
            return
        # Build response
        response = resp.build_response(req)

        conn.sendall(response)
        conn.close()

    @property
    def extract_cookies(self, req, resp):
        """
        Build cookies from the :class:`Request <Request>` headers.

        :param req:(Request) The :class:`Request <Request>` object.
        :param resp: (Response) The res:class:`Response <Response>` object.
        :rtype: cookies - A dictionary of cookie key-value pairs.
        """
        cookies = {}
        for header in req.headers:
            if header.startswith("Cookie:"):
                cookie_str = header.split(":", 1)[1].strip()
                for pair in cookie_str.split(";"):
                    key, value = pair.strip().split("=")
                    cookies[key] = value
        return cookies

    def build_response(self, req, resp):
        """Builds a :class:`Response <Response>` object 

        :param req: The :class:`Request <Request>` used to generate the response.
        :param resp: The  response object.
        :rtype: Response
        """
        response = Response()

        # Set default encoding for response
        response.encoding = 'utf-8' 
        response.raw = resp
        response.reason = response.raw.reason

        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url

        # Add new cookies from the server.
        response.cookies = self.extract_cookies(req)

        # Give the Response some context.
        response.request = req
        response.connection = self

        return response

    def add_headers(self, request):
        """
        Add headers to the request.

        This method is intended to be overridden by subclasses to inject
        custom headers. It does nothing by default.

        
        :param request: :class:`Request <Request>` to add headers to.
        """
        pass

    def build_proxy_headers(self, proxy):
        """Returns a dictionary of the headers to add to any request sent
        through a proxy. 

        :class:`HttpAdapter <HttpAdapter>`.

        :param proxy: The url of the proxy being used for this request.
        :rtype: dict
        """
        headers = {}
        #
        # TODO: build your authentication here
        #       username, password =...
        # we provide dummy auth here
        #
        username, password = ("user1", "password")
    
        if username:
            headers["Proxy-Authorization"] = (username, password)

        return headers