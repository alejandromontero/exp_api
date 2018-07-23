'''
This class wrapps different messages sent to the user from the API
'''


class messenger(object):
    @staticmethod
    def message404(message):
        error = {}
        error["detail"] = message
        error["status"] = "404"
        return error

    @staticmethod
    def message409(message):
        error = {}
        error["detail"] = "The proposed change has ben declined because: "
        error["detail"] += message
        error["status"] = "409"
        return error

    @staticmethod
    def message200(message):
        success = {}
        success["status"] = "200"
        success["detail"] = message
        return success

    @staticmethod
    def general_error(message):
        error = {}
        error["status"] = "500"
        error["detail"] = message
        return error
