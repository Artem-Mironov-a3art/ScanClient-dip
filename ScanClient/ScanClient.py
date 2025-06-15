import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget,
    QTableView, QPushButton, QLineEdit, QLabel,
    QComboBox, QHBoxLayout, QMessageBox, QHeaderView
)
from PySide6.QtCore import Qt, QAbstractTableModel
import psycopg2
from psycopg2 import sql


class NetworkDevicesModel(QAbstractTableModel):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self._data = data or []
        self._headers = ["IP", "MAC", "First Seen", "Last Seen"]  

    def rowCount(self, parent=None):
        return len(self._data)

    def columnCount(self, parent=None):
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            columns = [
                'ip_address', 'mac_address',
                'first_seen', 'last_seen'
            ]
            field_name = columns[index.column()]
            return str(self._data[index.row()].get(field_name))
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section]
        return None


class NetworkScannerClient(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Network Scanner Client")
        self.setGeometry(100, 100, 800, 600)
    
        self.db_connection = psycopg2.connect(
            host="localhost",
            database="netscan",
            user="postgres",
            password="098068"
        )
    
        self.init_ui()
        self.load_networks()
        self.load_devices()

    def init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout()
    
        # Network selection
        network_layout = QHBoxLayout()
        network_layout.addWidget(QLabel("Network:"))
    
        self.network_combo = QComboBox()
        network_layout.addWidget(self.network_combo)
    
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_devices)
        network_layout.addWidget(self.refresh_btn)
    
        self.delete_network_btn = QPushButton("Delete Network")
        self.delete_network_btn.clicked.connect(self.delete_network)
        network_layout.addWidget(self.delete_network_btn)
    
        layout.addLayout(network_layout)
    
        # Add network controls
        add_network_layout = QHBoxLayout()
        add_network_layout.addWidget(QLabel("Add Network (CIDR):"))
    
        self.new_network_input = QLineEdit()
        self.new_network_input.setPlaceholderText("e.g. 192.168.1.0/24")
        add_network_layout.addWidget(self.new_network_input)
    
        self.add_network_btn = QPushButton("Add")
        self.add_network_btn.clicked.connect(self.add_network)
        add_network_layout.addWidget(self.add_network_btn)
    
        layout.addLayout(add_network_layout)
    
        # Devices table
        self.devices_table = QTableView()
        self.devices_model = NetworkDevicesModel()
        self.devices_table.setModel(self.devices_model)
    
        # ��������� ������������ ��������
        self.devices_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.devices_table)
    
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)

    def load_networks(self):
        try:
            with self.db_connection.cursor() as cursor:
                cursor.execute("""
                    SELECT id, network_cidr, is_active 
                    FROM scan_networks 
                    ORDER BY network_cidr
                """)
                networks = cursor.fetchall()
        
                self.network_combo.clear()
                for network_id, cidr, is_active in networks:
                    status = " (active)" if is_active else " (inactive)"
                    self.network_combo.addItem(f"{cidr}{status}", network_id)
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load networks: {str(e)}")

    def load_devices(self):
        network_id = self.network_combo.currentData()
        if not network_id:
            return
        
        try:
            with self.db_connection.cursor() as cursor:
                cursor.execute("""
                    SELECT ip_address, mac_address, vendor, 
                           first_seen, last_seen
                    FROM network_devices
                    WHERE network_id = %s
                    ORDER BY last_seen DESC
                """, (network_id,))
        
                devices = cursor.fetchall()
                formatted_data = []  # ����������� ������ � ������� ��� ��������
                for device in devices:
                    formatted_device = {
                        'ip_address': device[0],
                        'mac_address': device[1],
                        'first_seen': device[3],
                        'last_seen': device[4]
                    }
                    formatted_data.append(formatted_device)
        
                self.devices_model = NetworkDevicesModel(formatted_data)
                self.devices_table.setModel(self.devices_model)
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load devices: {str(e)}")

    def add_network(self):
        cidr = self.new_network_input.text().strip()
        if not cidr:
            QMessageBox.warning(self, "Warning", "Please enter a valid CIDR notation")
            return
        
        try:
            with self.db_connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO scan_networks (network_cidr)
                    VALUES (%s)
                    ON CONFLICT (network_cidr) DO NOTHING
                    RETURNING id
                """, (cidr,))
        
                if cursor.rowcount > 0:
                    self.db_connection.commit()
                    self.load_networks()
                    self.new_network_input.clear()
                    QMessageBox.information(self, "Success", "Network added successfully")
                else:
                    QMessageBox.warning(self, "Warning", "Network already exists")
        
        except Exception as e:
            self.db_connection.rollback()
            QMessageBox.critical(self, "Error", f"Failed to add network: {str(e)}")

    def delete_network(self):
        network_id = self.network_combo.currentData()
        if not network_id:
            QMessageBox.warning(self, "Warning", "Please select a network to delete")
            return
        
        # ������������� ��������
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Are you sure you want to delete this network and all its devices?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        try:
            with self.db_connection.cursor() as cursor:
                # �������� ��������� ������ ����
                cursor.execute(
                    "DELETE FROM network_devices WHERE network_id = %s",
                    (network_id,)
                )
            
                # �������� ����� ����
                cursor.execute(
                    "DELETE FROM scan_networks WHERE id = %s",
                    (network_id,)
                )
            
                self.db_connection.commit()
                self.load_networks()
                self.devices_model = NetworkDevicesModel()
                self.devices_table.setModel(self.devices_model)
                QMessageBox.information(self, "Success", "Network deleted successfully")
        
        except Exception as e:
            self.db_connection.rollback()
            QMessageBox.critical(self, "Error", f"Failed to delete network: {str(e)}")

    def closeEvent(self, event):
        self.db_connection.close()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NetworkScannerClient()
    window.show()
    sys.exit(app.exec())