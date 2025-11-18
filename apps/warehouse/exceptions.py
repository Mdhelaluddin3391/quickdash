class WarehouseAutomationError(Exception): pass
class OutOfStockError(WarehouseAutomationError): pass
class ReservationFailedError(WarehouseAutomationError): pass