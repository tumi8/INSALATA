import xmlrpc.client

class RpcConnection:
    """
    Class is used to wrap the connection to a XenServer.
    Storage of to use on the XenServer is hold, too.
    """

    def __init__(self, uri, user, passwd, storage=None):
        """
        Creates a RpcConnection and initializes username and password to connect to the XenServer.

        :param uri: xen-server address to conntect to
        :type uri: str

        :param user: username for login
        :type user: str

        :param passwd: password used for login
        :type passwd: str

        :param storage: Storage to use on XenServer. (Optional)
        :type storage: str
        """
        self.uri = uri
        self.user = user
        self.passwd = passwd
        self.storage = storage
        self.xen = None
        self.session = None

    def getDefaultStorage(self):
        """
        Get the name of the default storage.

        :returns: Name of default storage
        :rtype: str
        """
        return self.storage

    def getConnectionSession(self):
        """
        Establishes a connection with the currently specified Xen-Server and user credentials.

        :returns: Server reverence and session: (serverReference, sessionObject)
        :rtype: tuple
        """
        self.xen = xmlrpc.client.Server(self.uri)
        self.session = self.xen.session.login_with_password(self.user, self.passwd)['Value']

        return (self.xen, self.session)
    
    def logout(self):
        """
        Logout from Xen server RPC session.
        """
        self.xen.session.logout(self.session)
