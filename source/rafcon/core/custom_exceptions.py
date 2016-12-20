"""
.. module:: custom_exceptions
   :platform: Unix, Windows
   :synopsis: A module that holds all custom exceptions for the state machine core

.. moduleauthor:: Sebastian Brunner


"""


class LibraryNotFoundException(Exception):

    def __init__(self, message):
        """ A custom exception for the case when a library is not found

        :param message: the error message for the exception
        :return:
        """

        # Call the base class constructor with the parameters it needs
        super(LibraryNotFoundException, self).__init__(message)


class RecoveryModeException(ValueError):

    def __init__(self, message, do_delete_item):
        """ A custom exception for the case when a state machine cannot be loaded because the interface of a
        library state changed (e.g. a data port has another data type, or a data port/outcome is completely missing).
        It derives from the Value Error as it has to replace the Value Error at many positions especially where
        type and consistency checking is performed. As many unit test cases expect ValueErrors at specific points
        in the code deriving form the ValueError seems to be more convenient then doing if/else clauses everywhere.

        :param message: the error message for the exception
        :param do_delete_item: a flag to indicate if the error is critical and the state element has to be deleted
        :return:
        """

        self._do_delete_item = do_delete_item

        # Call the base class constructor with the parameters it needs
        super(RecoveryModeException, self).__init__(message)

    @property
    def do_delete_item(self):
        """Property for the do_delete_item field

        """
        return self._do_delete_item

    @do_delete_item.setter
    def do_delete_item(self, do_delete_item):
        self._do_delete_item = do_delete_item
