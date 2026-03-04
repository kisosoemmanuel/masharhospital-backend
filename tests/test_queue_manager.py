from src.queue_manager import QueueManager, Patient


def test_enqueue_dequeue_order():
    qm = QueueManager()

    qm.enqueue(Patient("Alice", 1), emergency=False)
    qm.enqueue(Patient("Bob", 2, emergency=True), emergency=True)
    qm.enqueue(Patient("Carol", 3), emergency=False)

    first = qm.dequeue()
    assert first.name == "Bob"

    second = qm.dequeue()
    assert second.name == "Alice"
    third = qm.dequeue()
    assert third.name == "Carol"
    assert qm.dequeue() is None


def test_len_and_peek():
    qm = QueueManager()
    assert len(qm) == 0
    assert qm.peek() is None

    qm.enqueue(Patient("Diane", 4, emergency=True), emergency=True)
    qm.enqueue(Patient("Eve", 5))
    assert len(qm) == 2
    assert qm.peek().name == "Diane"

    qm.dequeue()
    assert qm.peek().name == "Eve"


def test_clear():
    qm = QueueManager()
    qm.enqueue(Patient("X", 6, emergency=True), emergency=True)
    qm.enqueue(Patient("Y", 7))
    qm.clear()
    assert len(qm) == 0
    assert qm.dequeue() is None


def test_multiple_emergencies():
    qm = QueueManager()
    qm.enqueue(Patient("A", 8, emergency=True), emergency=True)
    qm.enqueue(Patient("B", 9, emergency=True), emergency=True)
    qm.enqueue(Patient("C", 10), emergency=False)

    assert qm.dequeue().name == "A"
    assert qm.dequeue().name == "B"
    assert qm.dequeue().name == "C"


def test_dequeue_empty():
    qm = QueueManager()
    assert qm.dequeue() is None

