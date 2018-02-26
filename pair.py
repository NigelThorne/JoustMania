import psmove
import os
import jm_dbus

class Pair():
    """
    Manage paring move controllers to the server
    """
    def __init__(self):
        """Use DBus to find bluetooth controllers"""
        self.hci_dict = jm_dbus.get_hci_dict()

        devices = self.hci_dict.values()
        self.bt_devices = {}
        for device in devices:
            self.bt_devices[device] = []

        self.refresh_addressed_per_device()

    def refresh_addressed_per_device(self):
        """
        Enumerate known devices

        For each device on each adapter, add the device's address to it's adapter's
        list of known devices
        """
        for hci, addr in self.hci_dict.items():
            self.bt_devices[addr] = jm_dbus.get_attached_addresses(hci)

    def update_adapters(self):
        """
        Rescan for bluetooth adapters that may not have existed on program launch
        """
        self.hci_dict = jm_dbus.get_hci_dict()

        for addr in self.hci_dict.values():
            if addr not in self.bt_devices.keys():
                self.bt_devices[addr] = []

        self.refresh_addressed_per_device()

    def check_if_not_paired(self, addr):
        """
        Early out when you find the address on a known device
        """
        for devs in self.bt_devices.keys():
            if addr in self.bt_devices[devs]:
                return False
        return True

    def get_lowest_bt_device(self):
        num = 9999999
        best_dev = ""
        print(self.bt_devices)
        for dev in self.bt_devices.keys():
            new_num = len(self.bt_devices[dev])
            if new_num < num:
                num = new_num
                best_dev = dev
        return best_dev

    def pair_move_by_usb(self, move):
        if move and move.get_serial():
            if move.connection_type == psmove.Conn_USB:
                self.refresh_addressed_per_device()
                if self.check_if_not_paired(move.get_serial().upper()):
                    move.pair_custom(self.get_lowest_bt_device())

    def enable_bt_scanning(self, on=True):
        bt_hcis = list(jm_dbus.get_hci_dict().keys())

        for hci in bt_hcis:
            if jm_dbus.enable_adapter(hci):
                self.update_adapters()
            if on:
                jm_dbus.enable_pairable(hci)
            else:
                jm_dbus.disable_pairable(hci)