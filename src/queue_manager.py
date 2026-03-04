class QueueManager:
    def __init__(self):
        self.emergency = [] 
        self.normal = []   

    def enqueue(self, item, emergency=False):
        if emergency:
            self.emergency.append(item)
        else:
            self.normal.append(item)

    def dequeue(self):
        if self.emergency:
            return self.emergency.pop(0)
        if self.normal:
            return self.normal.pop(0)
        return None

    def peek(self):
        if self.emergency:
            return self.emergency[0]
        if self.normal:
            return self.normal[0]
        return None

    def __len__(self):
        return len(self.emergency) + len(self.normal)

    def clear(self):
        self.emergency.clear()
        self.normal.clear()

class Patient:
    def __init__(self, name, id, emergency=False):
        self.name = name
        self.id = id
        self.condition = "emergency" if emergency else "normal"


def create_patient(name, id, emergency=False):
    return Patient(name, id, emergency)
