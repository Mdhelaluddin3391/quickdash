# apps/warehouse/exceptions.py

class WarehouseAutomationError(Exception):
    """Base class for WMS domain errors."""
    pass


class NoAvailableWarehouseError(WarehouseAutomationError):
    """Raised when no warehouse can fulfil given SKUs."""
    pass


class ReservationFailedError(WarehouseAutomationError):
    """Raised when reservation cannot be completed."""
    pass


class OutOfStockError(WarehouseAutomationError):
    """Raised when stock is not enough for requested qty."""
    pass
