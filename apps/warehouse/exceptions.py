# apps/warehouse/exceptions.py
class WarehouseAutomationError(Exception):
    pass

class NoAvailableWarehouseError(WarehouseAutomationError):
    pass

class ReservationFailedError(WarehouseAutomationError):
    pass
