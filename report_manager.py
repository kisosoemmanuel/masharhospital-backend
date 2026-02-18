# report_manager.py

class ReportManager:

    @staticmethod
    def generate_report(statistics, total_served_session):
        print("\n========== HOSPITAL QUEUE REPORT ==========")
        print(f"Total Patients Served (This Session): {total_served_session}")
        print(f"Emergency Patients Served: {statistics['emergency_served']}")
        print(f"Normal Patients Served: {statistics['normal_served']}")
        print(f"Patients Waiting in Emergency Queue: {statistics['waiting_emergency']}")  # noqa: E501
        print(f"Patients Waiting in Normal Queue: {statistics['waiting_normal']}")  # noqa: E501
        print("===========================================\n")
