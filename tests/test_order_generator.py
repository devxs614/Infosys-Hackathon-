from edge_server.simulation.order_generator import OrderGenerator


def test_seeded_generator_is_reproducible():
    left = OrderGenerator(42).schedule_shift(30)
    right = OrderGenerator(42).schedule_shift(30)
    assert [(item.created_minute, item.order.id, item.order.zone, item.order.courier_payout_mxn) for item in left] == [(item.created_minute, item.order.id, item.order.zone, item.order.courier_payout_mxn) for item in right]

