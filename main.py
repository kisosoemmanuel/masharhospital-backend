# main.py

from queue_manager import QueueManager          # Dev 1
from patient_service import register_patient    # Dev 2
from report_manager import ReportManager        # Yours


def display_menu():
    print("\n===== Hospital Patient Queue System =====")
    print("1. Register Patient")
    print("2. Serve Patient")
    print("3. View Queue Status")
    print("4. Generate Report")
    print("5. Exit")


def main():
    qm = QueueManager()          # Dev 1 class
    total_served_session = 0    # Your system state tracking

    while True:
        display_menu()
        choice = input("Select an option: ")

        if choice == "1":
            # Dev 2 handles registration
            patient = register_patient()

            # Dev 1 handles queueing
            qm.enqueue(patient)
            print("Patient successfully added to queue.")

        elif choice == "2":
            patient = qm.serve_patient()
            if patient:
                total_served_session += 1
                print(f"Now serving: {patient}")
            else:
                print("No patients in queue.")

        elif choice == "3":
            status = qm.get_queue_status()
            print("\n--- Current Queue Status ---")
            print(status)

        elif choice == "4":
            stats = qm.get_statistics()
            ReportManager.generate_report(stats, total_served_session)

        elif choice == "5":
            print("Exiting system...")
            break

        else:
            print("Invalid option. Try again.")


if __name__ == "__main__":
    main()
