"""Execution gateways — single entry points for trading operations."""

from gateway.trade_gateway import TradeGateway, trade_gateway

__all__ = ["TradeGateway", "trade_gateway"]