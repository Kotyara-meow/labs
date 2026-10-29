"""Лабораторная работа № 1. Учёт поликлиники.

В программе хранятся сведения о пациентах, врачах и приёмах.
Данные можно сохранить в JSON или XML. Для проверки есть режим --demo.

Пример запуска:
    python main.py --demo
"""
from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


# ============================================================================
# РАЗДЕЛ 1. ИСКЛЮЧЕНИЯ
# Здесь собраны ошибки, которые могут возникнуть при работе с данными.
# ============================================================================


class ClinicError(Exception):
    """Базовое исключение предметной области поликлиники."""


class EntityNotFoundError(ClinicError):
    """Запрошенная сущность не найдена."""


class DuplicateEntityError(ClinicError):
    """Сущность с таким идентификатором уже существует."""


class ValidationError(ClinicError):
    """Данные сущности не прошли проверку."""


class StorageError(ClinicError):
    """Ошибка чтения или записи файла данных."""


# ============================================================================
# РАЗДЕЛ 2. ВСПОМОГАТЕЛЬНЫЕ ПРОВЕРКИ
# ============================================================================

def _required(value: str, field_name: str) -> str:
    value = value.strip()
    if not value:
        raise ValidationError(f"Поле «{field_name}» не может быть пустым.")
    return value


def _positive_id(value: int, field_name: str = "ID") -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValidationError(f"{field_name} должен быть положительным целым числом.")
    return value


# ============================================================================
# РАЗДЕЛ 3. КЛАССЫ ПРЕДМЕТНОЙ ОБЛАСТИ
# dataclass автоматически создаёт конструктор и другие стандартные методы.
# ============================================================================

@dataclass
class Specialty:
    id: int
    name: str
    description: str = ""

    def __post_init__(self) -> None:
        _positive_id(self.id)
        self.name = _required(self.name, "Название специальности")


@dataclass
class Department:
    id: int
    name: str
    room: str

    def __post_init__(self) -> None:
        _positive_id(self.id)
        self.name = _required(self.name, "Название отделения")
        self.room = _required(self.room, "Кабинет")


@dataclass
class Patient:
    id: int
    full_name: str
    birth_date: str
    phone: str
    policy_number: str

    def __post_init__(self) -> None:
        _positive_id(self.id)
        self.full_name = _required(self.full_name, "ФИО пациента")
        self.phone = _required(self.phone, "Телефон")
        self.policy_number = _required(self.policy_number, "Номер полиса")
        try:
            datetime.strptime(self.birth_date, "%Y-%m-%d")
        except (TypeError, ValueError) as exc:
            raise ValidationError("Дата рождения должна быть в формате ГГГГ-ММ-ДД.") from exc


@dataclass
class Doctor:
    id: int
    full_name: str
    specialty_id: int
    department_id: int
    office_hours: str

    def __post_init__(self) -> None:
        _positive_id(self.id)
        _positive_id(self.specialty_id, "ID специальности")
        _positive_id(self.department_id, "ID отделения")
        self.full_name = _required(self.full_name, "ФИО врача")
        self.office_hours = _required(self.office_hours, "Часы приёма")


@dataclass
class Appointment:
    id: int
    patient_id: int
    doctor_id: int
    start_at: str
    purpose: str
    status: str = "Запланирован"

    ALLOWED_STATUSES = ("Запланирован", "Завершён", "Отменён")

    def __post_init__(self) -> None:
        for value, label in ((self.id, "ID"), (self.patient_id, "ID пациента"), (self.doctor_id, "ID врача")):
            _positive_id(value, label)
        self.purpose = _required(self.purpose, "Причина обращения")
        if self.status not in self.ALLOWED_STATUSES:
            raise ValidationError("Статус приёма должен быть: Запланирован, Завершён или Отменён.")
        try:
            datetime.strptime(self.start_at, "%Y-%m-%d %H:%M")
        except (TypeError, ValueError) as exc:
            raise ValidationError("Дата и время приёма должны быть в формате ГГГГ-ММ-ДД ЧЧ:ММ.") from exc


@dataclass
class MedicalRecord:
    id: int
    appointment_id: int
    diagnosis: str
    recommendations: str
    created_at: str

    def __post_init__(self) -> None:
        for value, label in ((self.id, "ID"), (self.appointment_id, "ID приёма")):
            _positive_id(value, label)
        self.diagnosis = _required(self.diagnosis, "Диагноз")
        self.recommendations = _required(self.recommendations, "Рекомендации")
        try:
            datetime.strptime(self.created_at, "%Y-%m-%d")
        except (TypeError, ValueError) as exc:
            raise ValidationError("Дата записи должна быть в формате ГГГГ-ММ-ДД.") from exc


@dataclass
class Prescription:
    id: int
    record_id: int
    medication: str
    dosage: str
    duration: str

    def __post_init__(self) -> None:
        for value, label in ((self.id, "ID"), (self.record_id, "ID медицинской записи")):
            _positive_id(value, label)
        self.medication = _required(self.medication, "Препарат")
        self.dosage = _required(self.dosage, "Дозировка")
        self.duration = _required(self.duration, "Продолжительность курса")


@dataclass
class Diagnosis:
    """Справочник диагнозов для учебной модели."""
    id: int
    name: str
    description: str = ""

    def __post_init__(self) -> None:
        _positive_id(self.id)
        self.name = _required(self.name, "Название диагноза")


@dataclass
class Service:
    """Медицинская услуга с ценой в рублях."""
    id: int
    name: str
    price: float
    description: str = ""

    def __post_init__(self) -> None:
        _positive_id(self.id)
        self.name = _required(self.name, "Название услуги")
        if isinstance(self.price, bool) or not isinstance(self.price, (int, float)) or self.price < 0:
            raise ValidationError("Цена услуги должна быть неотрицательным числом.")
        self.price = float(self.price)


@dataclass
class Schedule:
    """Рабочий интервал врача на определённые дни недели."""
    id: int
    doctor_id: int
    weekdays: str
    start_time: str
    end_time: str

    def __post_init__(self) -> None:
        _positive_id(self.id)
        _positive_id(self.doctor_id, "ID врача")
        self.weekdays = _required(self.weekdays, "Дни недели")
        try:
            start = datetime.strptime(self.start_time, "%H:%M")
            end = datetime.strptime(self.end_time, "%H:%M")
        except (TypeError, ValueError) as exc:
            raise ValidationError("Время расписания должно быть в формате ЧЧ:ММ.") from exc
        if start >= end:
            raise ValidationError("Время начала расписания должно быть раньше времени окончания.")


# ============================================================================
# РАЗДЕЛ 4. КЛАСС CLINIC — ОБЩЕЕ ХРАНИЛИЩЕ ДАННЫХ
# В этом классе собраны операции добавления, поиска, изменения и удаления.
# ============================================================================

@dataclass
class Clinic:
    name: str
    specialties: list[Specialty] = field(default_factory=list)
    departments: list[Department] = field(default_factory=list)
    patients: list[Patient] = field(default_factory=list)
    doctors: list[Doctor] = field(default_factory=list)
    appointments: list[Appointment] = field(default_factory=list)
    medical_records: list[MedicalRecord] = field(default_factory=list)
    prescriptions: list[Prescription] = field(default_factory=list)
    diagnoses: list[Diagnosis] = field(default_factory=list)
    services: list[Service] = field(default_factory=list)
    schedules: list[Schedule] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = _required(self.name, "Название поликлиники")

    def _add(self, collection: list[Any], entity: Any) -> None:
        if any(item.id == entity.id for item in collection):
            raise DuplicateEntityError(f"Сущность с ID {entity.id} уже существует.")
        collection.append(entity)

    def _find(self, collection: list[Any], entity_id: int, entity_name: str) -> Any:
        _positive_id(entity_id)
        for item in collection:
            if item.id == entity_id:
                return item
        raise EntityNotFoundError(f"{entity_name} с ID {entity_id} не найден(а).")

    # Методы добавления проверяют, что ID не повторяется.
    def add_specialty(self, item: Specialty) -> None:
        self._add(self.specialties, item)

    def add_department(self, item: Department) -> None:
        self._add(self.departments, item)

    def add_patient(self, item: Patient) -> None:
        self._add(self.patients, item)

    def add_doctor(self, item: Doctor) -> None:
        self._find(self.specialties, item.specialty_id, "Специальность")
        self._find(self.departments, item.department_id, "Отделение")
        self._add(self.doctors, item)
    def add_appointment(self, item: Appointment) -> None:
        # Перед добавлением приёма проверяем, что пациент и врач существуют.
        self._find(self.patients, item.patient_id, "Пациент")
        self._find(self.doctors, item.doctor_id, "Врач")
        self._add(self.appointments, item)

    def add_medical_record(self, item: MedicalRecord) -> None:
        self._find(self.appointments, item.appointment_id, "Приём")
        self._add(self.medical_records, item)

    def add_prescription(self, item: Prescription) -> None:
        self._find(self.medical_records, item.record_id, "Медицинская запись")
        self._add(self.prescriptions, item)

    def add_diagnosis(self, item: Diagnosis) -> None:
        self._add(self.diagnoses, item)

    def add_service(self, item: Service) -> None:
        self._add(self.services, item)

    def add_schedule(self, item: Schedule) -> None:
        self._find(self.doctors, item.doctor_id, "Врач")
        self._add(self.schedules, item)

    # Поиск используется и в других методах, чтобы не дублировать код.
    def find_patient(self, patient_id: int) -> Patient:
        return self._find(self.patients, patient_id, "Пациент")

    def find_doctor(self, doctor_id: int) -> Doctor:
        return self._find(self.doctors, doctor_id, "Врач")

    def find_appointment(self, appointment_id: int) -> Appointment:
        return self._find(self.appointments, appointment_id, "Приём")

    def update_patient(self, patient_id: int, *, full_name: str, birth_date: str, phone: str, policy_number: str) -> Patient:
        old = self.find_patient(patient_id)
        updated = Patient(patient_id, full_name, birth_date, phone, policy_number)
        old.full_name, old.birth_date, old.phone, old.policy_number = updated.full_name, updated.birth_date, updated.phone, updated.policy_number
        return old

    def delete_patient(self, patient_id: int) -> None:
        patient = self.find_patient(patient_id)
        if any(a.patient_id == patient_id for a in self.appointments):
            raise ValidationError("Нельзя удалить пациента, у которого есть приёмы. Сначала удалите связанные приёмы.")
        self.patients.remove(patient)

    def delete_appointment(self, appointment_id: int) -> None:
        appointment = self.find_appointment(appointment_id)
        if any(record.appointment_id == appointment_id for record in self.medical_records):
            raise ValidationError("Нельзя удалить приём, к которому привязана медицинская запись.")
        self.appointments.remove(appointment)

    def delete_doctor(self, doctor_id: int) -> None:
        doctor = self.find_doctor(doctor_id)
        if any(a.doctor_id == doctor_id for a in self.appointments):
            raise ValidationError("Нельзя удалить врача, у которого есть приёмы.")
        if any(s.doctor_id == doctor_id for s in self.schedules):
            raise ValidationError("Сначала удалите расписание врача.")
        self.doctors.remove(doctor)

    def update_appointment_status(self, appointment_id: int, status: str) -> None:
        appointment = self.find_appointment(appointment_id)
        if status not in Appointment.ALLOWED_STATUSES:
            raise ValidationError("Недопустимый статус приёма.")
        appointment.status = status

    def to_dict(self) -> dict[str, Any]:
        return {
            "clinic": self.name,
            "specialties": [asdict(x) for x in self.specialties],
            "departments": [asdict(x) for x in self.departments],
            "patients": [asdict(x) for x in self.patients],
            "doctors": [asdict(x) for x in self.doctors],
            "appointments": [asdict(x) for x in self.appointments],
            "medical_records": [asdict(x) for x in self.medical_records],
            "prescriptions": [asdict(x) for x in self.prescriptions],
            "diagnoses": [asdict(x) for x in self.diagnoses],
            "services": [asdict(x) for x in self.services],
            "schedules": [asdict(x) for x in self.schedules],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Clinic":
        try:
            clinic = cls(data["clinic"])
            for key, model, method in (
                ("specialties", Specialty, clinic.add_specialty),
                ("departments", Department, clinic.add_department),
                ("patients", Patient, clinic.add_patient),
                ("doctors", Doctor, clinic.add_doctor),
                ("appointments", Appointment, clinic.add_appointment),
                ("medical_records", MedicalRecord, clinic.add_medical_record),
                ("prescriptions", Prescription, clinic.add_prescription),
                ("diagnoses", Diagnosis, clinic.add_diagnosis),
                ("services", Service, clinic.add_service),
                ("schedules", Schedule, clinic.add_schedule),
            ):
                for raw in data[key]:
                    method(model(**raw))
            return clinic
        except KeyError as exc:
            raise ValidationError(f"В файле отсутствует обязательное поле: {exc}.") from exc
        except TypeError as exc:
            raise ValidationError(f"Структура данных не соответствует модели: {exc}.") from exc

    def save_json(self, filename: str | Path) -> None:
        try:
            path = Path(filename)
            # Если каталога ещё нет, создаём его перед записью файла.
            path.parent.mkdir(parents=True, exist_ok=True)
            text = json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
            path.write_text(text, encoding="utf-8")
        except (OSError, TypeError, ValueError) as exc:
            raise StorageError(f"Не удалось записать JSON-файл: {exc}") from exc

    @classmethod
    def load_json(cls, filename: str | Path) -> "Clinic":
        try:
            data = json.loads(Path(filename).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValidationError("Корень JSON должен быть объектом.")
            return cls.from_dict(data)
        except FileNotFoundError as exc:
            raise StorageError(f"JSON-файл не найден: {filename}") from exc
        except json.JSONDecodeError as exc:
            raise StorageError(f"Ошибка синтаксиса JSON, строка {exc.lineno}: {exc.msg}") from exc
        except OSError as exc:
            raise StorageError(f"Не удалось прочитать JSON: {exc}") from exc

    def save_xml(self, filename: str | Path) -> None:
        try:
            root = ET.Element("clinic", {"name": self.name})
            # Названия тегов в XML пишутся в единственном числе.
            item_tags = {
                "specialties": "specialty",
                "departments": "department",
                "patients": "patient",
                "doctors": "doctor",
                "appointments": "appointment",
                "medical_records": "medical_record",
                "prescriptions": "prescription",
                "diagnoses": "diagnosis",
                "services": "service",
                "schedules": "schedule",
            }
            for key in ("specialties", "departments", "patients", "doctors", "appointments", "medical_records", "prescriptions", "diagnoses", "services", "schedules"):
                group = ET.SubElement(root, key)
                for row in self.to_dict()[key]:
                    element = ET.SubElement(group, item_tags[key])
                    for field_name, value in row.items():
                        child = ET.SubElement(element, field_name)
                        child.text = str(value)

            ET.indent(root, space="  ")
            path = Path(filename)
            path.parent.mkdir(parents=True, exist_ok=True)
            ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        except (OSError, TypeError, ValueError, ET.ParseError) as exc:
            raise StorageError(f"Не удалось записать XML-файл: {exc}") from exc

    @classmethod
    def load_xml(cls, filename: str | Path) -> "Clinic":
        try:
            root = ET.parse(filename).getroot()
            data: dict[str, Any] = {"clinic": root.attrib["name"]}
            keys = ("specialties", "departments", "patients", "doctors", "appointments", "medical_records", "prescriptions", "diagnoses", "services", "schedules")
            int_fields = {"id", "specialty_id", "department_id", "patient_id", "doctor_id", "appointment_id", "record_id"}
            float_fields = {"price"}
            for key in keys:
                data[key] = []
                group = root.find(key)
                if group is not None:
                    for element in list(group):
                        row: dict[str, Any] = {}
                        for child in list(element):
                            value = child.text or ""
                            row[child.tag] = int(value) if child.tag in int_fields else (float(value) if child.tag in float_fields else value)
                        data[key].append(row)
            return cls.from_dict(data)
        except FileNotFoundError as exc:
            raise StorageError(f"XML-файл не найден: {filename}") from exc
        except ET.ParseError as exc:
            raise StorageError(f"Некорректный XML: {exc}") from exc
        except (KeyError, OSError, ValueError) as exc:
            raise StorageError(f"Не удалось прочитать XML: {exc}") from exc


# ============================================================================
# РАЗДЕЛ 5. ДЕМОНСТРАЦИОННЫЕ ДАННЫЕ И ВЫВОД РЕЗУЛЬТАТА
# ============================================================================

def create_demo_clinic() -> Clinic:
    """Создаёт небольшой набор данных, чтобы проверить работу программы."""
    clinic = Clinic("Городская поликлиника № 12")
    clinic.add_specialty(Specialty(1, "Терапия", "Первичная диагностика и лечение"))
    clinic.add_specialty(Specialty(2, "Кардиология", "Заболевания сердечно-сосудистой системы"))
    clinic.add_department(Department(1, "Терапевтическое отделение", "Кабинет 214"))
    clinic.add_department(Department(2, "Кардиологическое отделение", "Кабинет 307"))
    clinic.add_patient(Patient(1, "Иванов Иван Иванович", "1998-04-12", "+7-900-111-22-33", "0000 111111"))
    clinic.add_patient(Patient(2, "Петрова Анна Сергеевна", "1985-11-03", "+7-900-222-33-44", "0000 222222"))
    clinic.add_doctor(Doctor(1, "Смирнова Елена Викторовна", 1, 1, "Пн–Пт, 08:00–14:00"))
    clinic.add_doctor(Doctor(2, "Кузнецов Павел Андреевич", 2, 2, "Пн–Чт, 14:00–19:00"))
    clinic.add_appointment(Appointment(1, 1, 1, "2026-11-02 09:30", "Плановый осмотр"))
    clinic.add_appointment(Appointment(2, 2, 2, "2026-11-02 15:00", "Консультация кардиолога"))
    clinic.add_medical_record(MedicalRecord(1, 1, "ОРВИ (предварительно)", "Контроль состояния у лечащего врача", "2026-11-02"))
    clinic.add_prescription(Prescription(1, 1, "Пример препарата", "По назначению врача", "Согласно назначению"))
    clinic.add_diagnosis(Diagnosis(1, "ОРВИ", "Учебный пример записи диагноза"))
    clinic.add_diagnosis(Diagnosis(2, "Профилактический осмотр", "Учебный пример"))
    clinic.add_service(Service(1, "Первичный приём терапевта", 1200.0, "Демонстрационная стоимость"))
    clinic.add_service(Service(2, "Консультация кардиолога", 1800.0, "Демонстрационная стоимость"))
    clinic.add_schedule(Schedule(1, 1, "Пн–Пт", "08:00", "14:00"))
    clinic.add_schedule(Schedule(2, 2, "Пн–Чт", "14:00", "19:00"))
    return clinic


def print_summary(clinic: Clinic) -> None:
    print(f"\n{clinic.name}")
    print(f"Специальностей: {len(clinic.specialties)} | Отделений: {len(clinic.departments)}")
    print(f"Пациентов: {len(clinic.patients)} | Врачей: {len(clinic.doctors)} | Приёмов: {len(clinic.appointments)}")
    print(f"Диагнозов: {len(clinic.diagnoses)} | Услуг: {len(clinic.services)} | Расписаний: {len(clinic.schedules)}")
    for appointment in clinic.appointments:
        patient = clinic.find_patient(appointment.patient_id)
        doctor = clinic.find_doctor(appointment.doctor_id)
        print(f"  #{appointment.id}: {appointment.start_at} — {patient.full_name}; врач: {doctor.full_name}; {appointment.status}")


# ============================================================================
# РАЗДЕЛ 6. ЗАПУСК ПРОГРАММЫ
# ============================================================================

def main() -> int:
    # Параметры задаются при запуске, поэтому отдельное меню не требуется.
    parser = argparse.ArgumentParser(description="Учёт поликлиники (ЛР1)")
    parser.add_argument("--demo", action="store_true", help="создать демонстрационные данные и сохранить JSON/XML")
    parser.add_argument("--data", default="data", help="каталог файлов данных (по умолчанию data)")
    args = parser.parse_args()
    data_dir = Path(args.data)
    try:
        if args.demo:
            clinic = create_demo_clinic()
            clinic.save_json(data_dir / "clinic.json")
            clinic.save_xml(data_dir / "clinic.xml")
            print("Демонстрационные данные созданы и сохранены в JSON и XML.")
        else:
            json_path = data_dir / "clinic.json"
            clinic = Clinic.load_json(json_path) if json_path.exists() else create_demo_clinic()
            if not json_path.exists():
                print("Файл данных пока отсутствует; показаны демонстрационные данные.")
        print_summary(clinic)
        return 0
    except ClinicError as exc:
        print(f"Ошибка предметной области: {exc}", file=sys.stderr)
        return 1
    except (ValueError, TypeError) as exc:
        print(f"Ошибка входных данных: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nРабота прервана пользователем.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
