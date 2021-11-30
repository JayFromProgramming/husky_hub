from Utils.CoordinatorHost import CoordinatorHost
from Utils.CoordinatorClient import CoordinatorClient
from Utils import coprocessors


class Coordinator:

    def __init__(self, local):
        """
        Initialize the type of thermostat depending on if it is local or remote
        :param local: If the thermostat is local or remote
        """
        self.coprocessor = coprocessors.Coprocessor(["/dev/ttyACM1", "/dev/ttyACM0"], [9600, 9600], local)
        if local:
            print("Init Thermostat Host")
            self.coordinator = CoordinatorHost(self.coprocessor)
        else:
            print("Init Remote Thermostat")
            self.coordinator = CoordinatorClient()
