import io
from datetime import date, timedelta
from decimal  import Decimal
from typing   import Dict, List, Optional
from uuid     import UUID

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils  import get_column_letter
from fastapi         import HTTPException, status
from sqlalchemy.orm  import Session, joinedload

from app.core.enum              import MEDICINE_CATEGORY_ENUM, REPORT_TYPE_ENUM, STATUS_CODE_ENUM
from app.core.log               import logger
from app.models.base_data_model import DEPARTMENT_MODEL, MEDICINE_MODEL
from app.models.data_model      import (
    PATIENT_DISPENSING_ITEM_MODEL
    , PATIENT_DISPENSING_MODEL
    , REPORT_EXPORT_MODEL
    , STOCK_LEDGER_MODEL
)
from app.schemas.report_schema   import ReportGenerateRequest
from app.services.file_service   import FileService
from app.services.patient_service import PatientService


class ExcelReportService:
    """Generates Excel reports matching the hospital templates and stores them in Cloudflare R2."""

    XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    _THIN        = Side(border_style = "thin", color = "000000")
    _BORDER      = Border(left = _THIN, right = _THIN, top = _THIN, bottom = _THIN)
    _HEADER_FILL = PatternFill(start_color = "D9E1F2", end_color = "D9E1F2", fill_type = "solid")
    _FONT_TITLE  = Font(name = "Khmer OS Moul Light", size = 12, bold = True)
    _FONT_HEADER = Font(name = "Khmer OS Siemreap", size = 10, bold = True)
    _FONT_BODY   = Font(name = "Khmer OS Siemreap", size = 10)


    @staticmethod
    def _to_float(val: Optional[Decimal]) -> float:
        return float(val) if val is not None else 0.0


    @classmethod
    def _style_cell(cls, cell, font=None, align="center", border=False, fill=None):
        cell.font      = font or cls._FONT_BODY
        cell.alignment = Alignment(horizontal = align, vertical = "center", wrap_text = True)
        if border:
            cell.border = cls._BORDER
        if fill:
            cell.fill = fill


    @classmethod
    def _build_daily_usage(
        cls
        , session       : Session
        , dept          : DEPARTMENT_MODEL
        , category_code : str
        , target_date   : date
        , signers       : Dict[str, str]
    ) -> openpyxl.Workbook:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"

        meds = (
            session.query(MEDICINE_MODEL)
            .filter(
                MEDICINE_MODEL.category_code == category_code
                , MEDICINE_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , MEDICINE_MODEL.deleted_datetime.is_(None)
            )
            .order_by(MEDICINE_MODEL.sort_order, MEDICINE_MODEL.name)
            .all()
        )

        total_cols = 6 + len(meds)
        ws.merge_cells(
            start_row    = 1
            , start_column = 1
            , end_row    = 1
            , end_column = max(total_cols, 10)
        )
        title_cell = ws.cell(
            1
            , 1
            , f"របាយការណ៍ឪសថ បរិក្ខាពេទ្យ សំរាប់ឪសថយាម/ផ្នែកបច្ចេកទេស\n"
              f"ថ្ងៃទី {target_date.day:02d} ខែ {target_date.month:02d} ឆ្នាំ {target_date.year}    {dept.name_kh}"
        )
        cls._style_cell(title_cell, font = cls._FONT_TITLE, align = "center")
        ws.row_dimensions[1].height = 42

        base_headers = ["N°", "NAME", "AGE", "SEX", "Diagnostic", "Province"]
        med_col_map: Dict[UUID, int] = {}
        for idx, h in enumerate(base_headers, start = 1):
            c = ws.cell(3, idx, h)
            cls._style_cell(c, font = cls._FONT_HEADER, border = True, fill = cls._HEADER_FILL)

        for offset, med in enumerate(meds):
            col_idx = 7 + offset
            label   = f"{med.name} {med.dosage}".strip() if med.dosage else med.name
            c       = ws.cell(3, col_idx, label)
            cls._style_cell(c, font = cls._FONT_HEADER, border = True, fill = cls._HEADER_FILL)
            med_col_map[med.id] = col_idx

        records = (
            session.query(PATIENT_DISPENSING_MODEL)
            .options(joinedload(PATIENT_DISPENSING_MODEL.items))
            .filter(
                PATIENT_DISPENSING_MODEL.dispense_date == target_date
                , PATIENT_DISPENSING_MODEL.department_code == dept.code
                , PATIENT_DISPENSING_MODEL.category_code == category_code
                , PATIENT_DISPENSING_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , PATIENT_DISPENSING_MODEL.deleted_datetime.is_(None)
            )
            .order_by(
                PATIENT_DISPENSING_MODEL.patient_no
                , PATIENT_DISPENSING_MODEL.created_datetime
            )
            .all()
        )

        row_idx = 4
        for seq, rec in enumerate(records, start = 1):
            vals = [
                rec.patient_no or seq
                , rec.patient_name
                , rec.age
                , rec.sex
                , rec.diagnostic
                , rec.address_province
            ]
            for c_i, val in enumerate(vals, start = 1):
                c = ws.cell(row_idx, c_i, val)
                cls._style_cell(c, align = "left" if c_i in (2, 5, 6) else "center", border = True)

            for c_i in range(7, total_cols + 1):
                cls._style_cell(ws.cell(row_idx, c_i, None), border = True)

            for item in rec.items:
                if item.medicine_id in med_col_map and item.deleted_datetime is None:
                    c_i = med_col_map[item.medicine_id]
                    c   = ws.cell(row_idx, c_i, cls._to_float(item.quantity))
                    cls._style_cell(c, border = True)
            row_idx += 1

        footer_row = row_idx + 1
        duty_chief = signers.get("duty_chief", "ប្រធានយាម")
        preparer   = signers.get("prepared_by", "អ្នកធ្វើតារាង")
        ws.cell(footer_row, 2, duty_chief).font = cls._FONT_HEADER
        ws.cell(footer_row, 8, preparer).font   = cls._FONT_HEADER
        return wb


    @classmethod
    def _build_daily_stock(
        cls
        , session       : Session
        , dept          : DEPARTMENT_MODEL
        , category_code : str
        , target_date   : date
    ) -> openpyxl.Workbook:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"

        ws.merge_cells("A1:I1")
        cls._style_cell(
            ws.cell(1, 1, "ព្រះរាជាណាចក្រកម្ពុជា\nជាតិ សាសនា ព្រះមហាក្សត្រ")
            , font = cls._FONT_TITLE
        )
        ws.row_dimensions[1].height = 36

        ws.merge_cells("A2:D3")
        cls._style_cell(
            ws.cell(
                2
                , 1
                , f"ក្រសួងសុខាភិបាល\n{dept.hospital_name_kh or 'មន្ទីរពេទ្យមិត្តភាពខ្មែរ-សូវៀត'}\n{dept.name_kh}"
            )
            , font  = cls._FONT_HEADER
            , align = "left"
        )

        ws.merge_cells("A6:I6")
        cls._style_cell(
            ws.cell(
                6
                , 1
                , f"របាយការណ៍ ចំណូល-ចំណាយ សម្ភារៈបរិក្ខាពេទ្យ-ឪសថប្រចាំថ្ងៃ\n"
                  f"ប្រចាំថ្ងៃទី {target_date.day:02d} ខែ {target_date.month:02d} ឆ្នាំ {target_date.year}"
            )
            , font = cls._FONT_TITLE
        )
        ws.row_dimensions[6].height = 36

        headers = [
            "ល.រ"
            , "សំភារ ឪសថ និងបរិក្ខា"
            , "ប្រភេទ"
            , "កំរិត"
            , "ចំនួនសល់ពីមុន"
            , "ចំនួនបន្ថែម"
            , "ចំនួនសរុប"
            , "ចំនួនសល់"
            , "ផ្សេងៗ"
        ]
        for idx, h in enumerate(headers, start = 1):
            cls._style_cell(ws.cell(8, idx, h), font = cls._FONT_HEADER, border = True, fill = cls._HEADER_FILL)

        meds = (
            session.query(MEDICINE_MODEL)
            .filter(
                MEDICINE_MODEL.category_code == category_code
                , MEDICINE_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , MEDICINE_MODEL.deleted_datetime.is_(None)
            )
            .order_by(MEDICINE_MODEL.sort_order, MEDICINE_MODEL.name)
            .all()
        )
        ledgers = (
            session.query(STOCK_LEDGER_MODEL)
            .filter(
                STOCK_LEDGER_MODEL.stock_date == target_date
                , STOCK_LEDGER_MODEL.department_code == dept.code
                , STOCK_LEDGER_MODEL.deleted_datetime.is_(None)
            )
            .all()
        )
        ledger_map = {l.medicine_id: l for l in ledgers}

        for seq, med in enumerate(meds, start = 1):
            r          = 8 + seq
            lg         = ledger_map.get(med.id)
            opening    = cls._to_float(lg.opening_qty) if lg else 0.0
            added      = cls._to_float(lg.added_qty) if lg else 0.0
            remaining  = cls._to_float(lg.remaining_qty) if lg else (opening + added)
            note       = lg.note if lg else None
            form_label = med.form.name if med.form else med.form_code

            row_vals = [
                seq
                , med.name
                , form_label
                , med.dosage
                , opening
                , added
                , f"=E{r}+F{r}"
                , remaining
                , note
            ]
            for c_i, val in enumerate(row_vals, start = 1):
                cls._style_cell(
                    ws.cell(r, c_i, val)
                    , align  = "left" if c_i == 2 else "center"
                    , border = True
                )

        ws.column_dimensions["B"].width = 28
        for col_ltr in ["E", "F", "G", "H", "I"]:
            ws.column_dimensions[col_ltr].width = 16
        return wb


    @classmethod
    def _build_weekly_usage_request(
        cls
        , session       : Session
        , dept          : DEPARTMENT_MODEL
        , category_code : str
        , start_date    : date
        , end_date      : date
        , signers       : Dict[str, str]
    ) -> openpyxl.Workbook:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "ឱសថ"

        days: List[date] = []
        cur = start_date
        while cur <= end_date:
            days.append(cur)
            cur += timedelta(days = 1)

        day_count  = len(days)
        total_cols = 11 + day_count  # B..G (6) + days + 4 trailing (total_used, remaining, requested, supplied)

        for r, text in [
            (1, dept.hospital_name_kh or "មន្ទីរពេទ្យមិត្តភាពខ្មែរ-សូវៀត")
            , (2, dept.name_kh)
            , (3, "របាយការណ៍ចំណូលចំណាយ និងសំណើឱសថ")
            , (
                4
                , f"ចាប់ពីថ្ងៃទី {start_date.day:02d} ខែ {start_date.month:02d} ឆ្នាំ {start_date.year} "
                  f"ដល់ថ្ងៃទី {end_date.day:02d} ខែ {end_date.month:02d} ឆ្នាំ {end_date.year}"
            )
        ]:
            ws.merge_cells(start_row = r, start_column = 2, end_row = r, end_column = total_cols)
            cls._style_cell(ws.cell(r, 2, text), font = cls._FONT_TITLE)

        fixed_left = ["ល.រ", "ឱសថ", "ប្រភេទ", "កម្រិត", "ដើមគ្រា", "ចំណូល"]
        for idx, h in enumerate(fixed_left, start = 2):
            ws.merge_cells(start_row = 5, start_column = idx, end_row = 6, end_column = idx)
            cls._style_cell(ws.cell(5, idx, h), font = cls._FONT_HEADER, border = True, fill = cls._HEADER_FILL)
            cls._style_cell(ws.cell(6, idx, None), border = True, fill = cls._HEADER_FILL)

        day_start_col = 8
        day_end_col   = day_start_col + day_count - 1
        ws.merge_cells(start_row = 5, start_column = day_start_col, end_row = 5, end_column = day_end_col)
        cls._style_cell(
            ws.cell(5, day_start_col, "បរិមាណប្រើប្រាស់")
            , font   = cls._FONT_HEADER
            , border = True
            , fill   = cls._HEADER_FILL
        )
        for c_i, d in enumerate(days, start = day_start_col):
            cls._style_cell(ws.cell(5, c_i, ws.cell(5, c_i).value), font = cls._FONT_HEADER, border = True, fill = cls._HEADER_FILL)
            cls._style_cell(ws.cell(6, c_i, d.day), font = cls._FONT_HEADER, border = True, fill = cls._HEADER_FILL)

        trailing = ["ចំណាយសរុប", "ចំនួនសល់", "ចំនួនស្នើសុំ", "ចំនួនផ្ដល់"]
        for offset, h in enumerate(trailing):
            col_i = day_end_col + 1 + offset
            ws.merge_cells(start_row = 5, start_column = col_i, end_row = 6, end_column = col_i)
            cls._style_cell(ws.cell(5, col_i, h), font = cls._FONT_HEADER, border = True, fill = cls._HEADER_FILL)
            cls._style_cell(ws.cell(6, col_i, None), border = True, fill = cls._HEADER_FILL)

        meds = (
            session.query(MEDICINE_MODEL)
            .filter(
                MEDICINE_MODEL.category_code == category_code
                , MEDICINE_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , MEDICINE_MODEL.deleted_datetime.is_(None)
            )
            .order_by(MEDICINE_MODEL.sort_order, MEDICINE_MODEL.name)
            .all()
        )
        ledgers = (
            session.query(STOCK_LEDGER_MODEL)
            .filter(
                STOCK_LEDGER_MODEL.department_code == dept.code
                , STOCK_LEDGER_MODEL.stock_date >= start_date
                , STOCK_LEDGER_MODEL.stock_date <= end_date
                , STOCK_LEDGER_MODEL.deleted_datetime.is_(None)
            )
            .order_by(STOCK_LEDGER_MODEL.stock_date)
            .all()
        )
        ledger_by_med_date: Dict[tuple, STOCK_LEDGER_MODEL] = {
            (l.medicine_id, l.stock_date): l for l in ledgers
        }

        start_ltr    = get_column_letter(day_start_col)
        end_ltr      = get_column_letter(day_end_col)
        used_sum_ltr = get_column_letter(day_end_col + 1)

        row_idx = 7
        for seq, med in enumerate(meds, start = 1):
            med_ledgers = [ledger_by_med_date.get((med.id, d)) for d in days]
            first_lg    = next((l for l in med_ledgers if l is not None), None)
            opening     = cls._to_float(first_lg.opening_qty) if first_lg else 0.0
            income      = sum(cls._to_float(l.added_qty) for l in med_ledgers if l is not None)
            requested   = sum(cls._to_float(l.requested_qty) for l in med_ledgers if l is not None)
            supplied    = sum(cls._to_float(l.supplied_qty) for l in med_ledgers if l is not None)
            form_label  = med.form.name if med.form else med.form_code

            cls._style_cell(ws.cell(row_idx, 2, seq), border = True)
            cls._style_cell(ws.cell(row_idx, 3, med.name), align = "left", border = True)
            cls._style_cell(ws.cell(row_idx, 4, form_label), border = True)
            cls._style_cell(ws.cell(row_idx, 5, med.dosage), border = True)
            cls._style_cell(ws.cell(row_idx, 6, opening), border = True)
            cls._style_cell(ws.cell(row_idx, 7, income if income else None), border = True)

            for offset, d in enumerate(days):
                lg   = ledger_by_med_date.get((med.id, d))
                used = cls._to_float(lg.used_qty) if lg and lg.used_qty else None
                cls._style_cell(ws.cell(row_idx, day_start_col + offset, used), border = True)

            cls._style_cell(
                ws.cell(row_idx, day_end_col + 1, f"=SUM({start_ltr}{row_idx}:{end_ltr}{row_idx})")
                , border = True
            )
            cls._style_cell(
                ws.cell(row_idx, day_end_col + 2, f"=SUM(F{row_idx}:G{row_idx})-{used_sum_ltr}{row_idx}")
                , border = True
            )
            cls._style_cell(ws.cell(row_idx, day_end_col + 3, requested if requested else None), border = True)
            cls._style_cell(ws.cell(row_idx, day_end_col + 4, supplied if supplied else None), border = True)
            row_idx += 1

        footer_r = row_idx + 2
        ws.cell(footer_r, 3, signers.get("director", "នាយកមន្ទីរពេទ្យ")).font = cls._FONT_HEADER
        ws.cell(footer_r, day_end_col, signers.get("pharmacist", "មន្ត្រីគ្រប់គ្រងឱសថ")).font = cls._FONT_HEADER
        ws.column_dimensions["C"].width = 26
        return wb


    @classmethod
    def _build_narcotic_usage(
        cls
        , session     : Session
        , dept        : DEPARTMENT_MODEL
        , start_date  : date
        , end_date    : date
        , medicine_id : Optional[UUID]
        , signers     : Dict[str, str]
    ) -> openpyxl.Workbook:
        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        med_query = session.query(MEDICINE_MODEL).filter(
            MEDICINE_MODEL.is_narcotic.is_(True)
            , MEDICINE_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
            , MEDICINE_MODEL.deleted_datetime.is_(None)
        )
        if medicine_id:
            med_query = med_query.filter(MEDICINE_MODEL.id == medicine_id)
        narcotics = med_query.order_by(MEDICINE_MODEL.sort_order).all()

        if not narcotics:
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "No narcotic medicines found."
            )

        for med in narcotics:
            sheet_title = f"{med.name} {med.dosage or ''}".strip()[:31]
            ws          = wb.create_sheet(title = sheet_title)

            ws.merge_cells("A1:J1")
            cls._style_cell(ws.cell(1, 1, dept.hospital_name_kh or "មន្ទីរពេទ្យមិត្តភាពខ្មែរ-សូវៀត"), font = cls._FONT_TITLE)
            ws.merge_cells("A2:J2")
            cls._style_cell(ws.cell(2, 1, f"ផ្នែក៖{dept.name_kh}"), font = cls._FONT_HEADER)
            ws.cell(3, 1, f"លេខ៖{med.narcotic_doc_no or dept.doc_number or '101'}").font = cls._FONT_HEADER
            ws.merge_cells("A4:J4")
            cls._style_cell(
                ws.cell(4, 1, f"របាយការណ៍ប្រើប្រាស់ឱសថមានសារធាតុញៀន {med.name} {med.dosage or ''}".strip())
                , font = cls._FONT_TITLE
            )

            headers = [
                "ល.រ"
                , "ថ្ងៃ/ទី/ខែ"
                , "ឈ្មោះអ្នកជំងឺ"
                , "អាយុ"
                , "ភេទ"
                , "អាស័យដ្ឋាន"
                , "ចំនួនប្រើ"
                , "រោគវិនិច្ឆ័យ"
                , "ឈ្មោះគ្រូពេទ្យ"
                , "ហត្ថលេខា"
            ]
            for c_i, h in enumerate(headers, start = 1):
                cls._style_cell(ws.cell(5, c_i, h), font = cls._FONT_HEADER, border = True, fill = cls._HEADER_FILL)

            items = (
                session.query(PATIENT_DISPENSING_ITEM_MODEL)
                .join(PATIENT_DISPENSING_MODEL, PATIENT_DISPENSING_ITEM_MODEL.dispensing_id == PATIENT_DISPENSING_MODEL.id)
                .options(joinedload(PATIENT_DISPENSING_ITEM_MODEL.dispensing))
                .filter(
                    PATIENT_DISPENSING_ITEM_MODEL.medicine_id == med.id
                    , PATIENT_DISPENSING_ITEM_MODEL.deleted_datetime.is_(None)
                    , PATIENT_DISPENSING_MODEL.department_code == dept.code
                    , PATIENT_DISPENSING_MODEL.dispense_date >= start_date
                    , PATIENT_DISPENSING_MODEL.dispense_date <= end_date
                    , PATIENT_DISPENSING_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                    , PATIENT_DISPENSING_MODEL.deleted_datetime.is_(None)
                )
                .order_by(
                    PATIENT_DISPENSING_MODEL.dispense_date
                    , PATIENT_DISPENSING_MODEL.created_datetime
                )
                .all()
            )

            row_idx    = 6
            total_used = 0.0
            for seq, it in enumerate(items, start = 1):
                d   = it.dispensing
                qty = cls._to_float(it.quantity)
                total_used += qty
                vals = [
                    seq
                    , d.dispense_date.strftime("%d/%m/%Y")
                    , d.patient_name
                    , d.age
                    , d.sex
                    , d.address_province
                    , qty
                    , d.diagnostic
                    , d.doctor_name
                    , it.signature_note
                ]
                for c_i, v in enumerate(vals, start = 1):
                    cls._style_cell(
                        ws.cell(row_idx, c_i, v)
                        , align  = "left" if c_i in (3, 6, 8, 9) else "center"
                        , border = True
                    )
                row_idx += 1

            unit_lbl = med.unit_label or "អំពូល"
            ws.merge_cells(start_row = row_idx, start_column = 1, end_row = row_idx, end_column = 10)
            cls._style_cell(
                ws.cell(row_idx, 1, f"ចំនួនប្រើប្រាស់សរុបៈ\u200b {int(total_used) if total_used.is_integer() else total_used}{unit_lbl}")
                , font  = cls._FONT_HEADER
                , align = "left"
            )
            ws.cell(row_idx + 1, 9, f"ថ្ងៃទី {end_date.day:02d} ខែ {end_date.month:02d} ឆ្នាំ {end_date.year}").font = cls._FONT_BODY
            ws.cell(row_idx + 2, 2, signers.get("director", "នាយកមន្ទីរពេទ្យ")).font                                   = cls._FONT_HEADER
            ws.cell(row_idx + 2, 6, signers.get("pharmacist", "បានពិនិត្យដោយមន្ត្រីគ្រប់គ្រងឱសថ")).font                  = cls._FONT_HEADER
            ws.cell(row_idx + 2, 9, signers.get("department_chief", "ហត្ថលេខានាយផ្នែក")).font                             = cls._FONT_HEADER

            for col_ltr, w in [("C", 22), ("F", 20), ("H", 22), ("I", 20)]:
                ws.column_dimensions[col_ltr].width = w

        return wb


    @classmethod
    def _build_patient_usage_matrix(
        cls
        , session       : Session
        , dept          : DEPARTMENT_MODEL
        , category_code : str
        , start_date    : date
        , end_date      : date
        , patient_id    : Optional[UUID]
        , signers       : Dict[str, str]
    ) -> openpyxl.Workbook:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"

        meds = (
            session.query(MEDICINE_MODEL)
            .filter(
                MEDICINE_MODEL.category_code == category_code
                , MEDICINE_MODEL.status_code == STATUS_CODE_ENUM.ACTIVE.value
                , MEDICINE_MODEL.deleted_datetime.is_(None)
            )
            .order_by(MEDICINE_MODEL.sort_order, MEDICINE_MODEL.name)
            .all()
        )

        total_cols = 6 + len(meds)
        ws.merge_cells(
            start_row    = 1
            , start_column = 1
            , end_row    = 1
            , end_column = max(total_cols, 10)
        )
        date_label = (
            f"ថ្ងៃទី {start_date.day:02d}/{start_date.month:02d}/{start_date.year}"
            if start_date == end_date
            else f"ចាប់ពី {start_date.strftime('%d/%m/%Y')} ដល់ {end_date.strftime('%d/%m/%Y')}"
        )
        title_cell = ws.cell(
            1
            , 1
            , f"របាយការណ៍ឪសថ បរិក្ខាពេទ្យ សំរាប់ឪសថយាម/ផ្នែកបច្ចេកទេស\n{date_label}    {dept.name_kh}"
        )
        cls._style_cell(title_cell, font = cls._FONT_TITLE, align = "center")
        ws.row_dimensions[1].height = 42

        base_headers = ["N°", "NAME", "AGE", "SEX", "Diagnostic", "Province"]
        med_col_map: Dict[UUID, int] = {}
        for idx, h in enumerate(base_headers, start = 1):
            c = ws.cell(3, idx, h)
            cls._style_cell(c, font = cls._FONT_HEADER, border = True, fill = cls._HEADER_FILL)

        for offset, med in enumerate(meds):
            col_idx = 7 + offset
            label   = f"{med.name} {med.dosage}".strip() if med.dosage else med.name
            c       = ws.cell(3, col_idx, label)
            cls._style_cell(c, font = cls._FONT_HEADER, border = True, fill = cls._HEADER_FILL)
            med_col_map[med.id] = col_idx

        patient_reports = PatientService.get_patient_usage_report(
            session      = session
            , start_date = start_date
            , period     = "DAILY"
            , end_date   = end_date
            , patient_id = patient_id
        )

        row_idx = 4
        for seq, pr in enumerate(patient_reports, start = 1):
            vals = [seq, pr.patient_name, pr.age, pr.sex, pr.diagnostic, pr.pob_province]
            for c_i, val in enumerate(vals, start = 1):
                cls._style_cell(
                    ws.cell(row_idx, c_i, val)
                    , align  = "left" if c_i in (2, 5, 6) else "center"
                    , border = True
                )
            for c_i in range(7, total_cols + 1):
                cls._style_cell(ws.cell(row_idx, c_i, None), border = True)

            for m_item in pr.medicines:
                if m_item.medicine_id in med_col_map:
                    c_i = med_col_map[m_item.medicine_id]
                    cls._style_cell(ws.cell(row_idx, c_i, cls._to_float(m_item.total_quantity)), border = True)
            row_idx += 1

        footer_row = row_idx + 1
        ws.cell(footer_row, 2, signers.get("duty_chief", "ប្រធានយាម")).font = cls._FONT_HEADER
        ws.cell(footer_row, 8, signers.get("prepared_by", "អ្នកធ្វើតារាង")).font = cls._FONT_HEADER
        return wb


    @classmethod
    def generate_report(
        cls
        , session  : Session
        , payload  : ReportGenerateRequest
        , username : str
    ) -> REPORT_EXPORT_MODEL:
        dept = (
            session.query(DEPARTMENT_MODEL)
            .filter(DEPARTMENT_MODEL.code == payload.department_code)
            .first()
        )
        if not dept:
            logger.warn(
                "ExcelReportService.generate_report: department not found"
                , f"department_code: {payload.department_code}"
                , f"username: {username}"
            )
            raise HTTPException(
                status_code = status.HTTP_404_NOT_FOUND
                , detail    = "Department not found."
            )

        logger.info(
            "ExcelReportService.generate_report: starting"
            , f"report_type: {payload.report_type_code}"
            , f"department_code: {payload.department_code}"
            , f"period: {payload.period}"
            , f"username: {username}"
        )

        start_date, end_date = PatientService.resolve_period_range(
            start_date   = payload.start_date
            , period     = payload.period
            , end_date   = payload.end_date
        )
        category_code = payload.category_code or MEDICINE_CATEGORY_ENUM.INJECTION.value
        signers       = payload.signers or {}

        if payload.report_type_code == REPORT_TYPE_ENUM.DAILY_USAGE.value:
            wb    = cls._build_daily_usage(session, dept, category_code, start_date, signers)
            fname = f"daily_usage_{category_code.lower()}_{start_date.isoformat()}"
        elif payload.report_type_code == REPORT_TYPE_ENUM.DAILY_STOCK.value:
            wb    = cls._build_daily_stock(session, dept, category_code, start_date)
            fname = f"daily_stock_{category_code.lower()}_{start_date.isoformat()}"
        elif payload.report_type_code == REPORT_TYPE_ENUM.WEEKLY_USAGE_REQUEST.value:
            wb    = cls._build_weekly_usage_request(session, dept, category_code, start_date, end_date, signers)
            fname = f"usage_request_{payload.period.lower()}_{category_code.lower()}_{start_date.isoformat()}_{end_date.isoformat()}"
        elif payload.report_type_code == REPORT_TYPE_ENUM.NARCOTIC_USAGE.value:
            wb    = cls._build_narcotic_usage(session, dept, start_date, end_date, payload.medicine_id, signers)
            fname = f"narcotic_usage_{payload.period.lower()}_{start_date.isoformat()}_{end_date.isoformat()}"
        elif payload.report_type_code == REPORT_TYPE_ENUM.PATIENT_USAGE.value:
            wb    = cls._build_patient_usage_matrix(
                session         = session
                , dept          = dept
                , category_code = category_code
                , start_date    = start_date
                , end_date      = end_date
                , patient_id    = payload.patient_id
                , signers       = signers
            )
            fname = f"patient_usage_{payload.period.lower()}_{category_code.lower()}_{start_date.isoformat()}_{end_date.isoformat()}"
        else:
            logger.warn(
                "ExcelReportService.generate_report: unsupported report_type_code"
                , f"report_type: {payload.report_type_code}"
            )
            raise HTTPException(
                status_code = status.HTTP_400_BAD_REQUEST
                , detail    = f"Unsupported report_type_code: {payload.report_type_code}"
            )

        buf = io.BytesIO()
        wb.save(buf)
        xlsx_bytes = buf.getvalue()

        file_obj = FileService.upload_and_register(
            session      = session
            , content    = xlsx_bytes
            , filename   = fname
            , ext        = ".xlsx"
            , mime_type  = cls.XLSX_MIME
            , title      = fname
            , module     = "reports"
            , created_by = username
        )

        export_row = REPORT_EXPORT_MODEL(
            report_type_code  = payload.report_type_code
            , department_code = dept.code
            , category_code   = payload.category_code
            , medicine_id     = payload.medicine_id
            , start_date      = payload.start_date
            , end_date        = end_date
            , file_object_id  = file_obj.id
            , signers_json    = signers
            , created_by      = username
        )
        session.add(export_row)
        session.commit()
        session.refresh(export_row)
        export_row.file_object = file_obj
        logger.info(
            "ExcelReportService.generate_report: completed"
            , f"export_id: {export_row.id}"
            , f"report_type: {payload.report_type_code}"
            , f"filename: {fname}.xlsx"
            , f"size: {len(xlsx_bytes)}"
            , f"username: {username}"
        )
        return export_row
