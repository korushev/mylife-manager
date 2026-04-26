from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.app.database import get_connection, row_to_dict
from backend.app.routers.utils import new_id, utc_now
from backend.app.schemas import (
    CRMContactCreate,
    CRMContactOut,
    CRMContactUpdate,
    CRMDealCreate,
    CRMDealOut,
    CRMDealUpdate,
)

router = APIRouter(prefix="/api/crm", tags=["crm"])


@router.get("/contacts", response_model=list[CRMContactOut])
def list_contacts() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            (
                "SELECT id, full_name, email, phone, company, note, created_at, updated_at "
                "FROM crm_contacts ORDER BY created_at DESC"
            )
        ).fetchall()
    return [row_to_dict(row) for row in rows]


@router.post("/contacts", response_model=CRMContactOut, status_code=201)
def create_contact(payload: CRMContactCreate) -> dict:
    contact_id = new_id()
    now = utc_now()
    with get_connection() as conn:
        conn.execute(
            (
                "INSERT INTO crm_contacts "
                "(id, full_name, email, phone, company, note, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            (
                contact_id,
                payload.full_name,
                payload.email,
                payload.phone,
                payload.company,
                payload.note,
                now,
                now,
            ),
        )
        row = conn.execute(
            (
                "SELECT id, full_name, email, phone, company, note, created_at, updated_at "
                "FROM crm_contacts WHERE id = ?"
            ),
            (contact_id,),
        ).fetchone()
    return row_to_dict(row)


@router.patch("/contacts/{contact_id}", response_model=CRMContactOut)
def update_contact(contact_id: str, payload: CRMContactUpdate) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    with get_connection() as conn:
        exists = conn.execute(
            "SELECT id FROM crm_contacts WHERE id = ?", (contact_id,)
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Contact not found")

        fields: list[str] = []
        values: list[str | None] = []
        for key, value in updates.items():
            fields.append(f"{key} = ?")
            values.append(value)
        fields.append("updated_at = ?")
        values.append(utc_now())
        values.append(contact_id)

        conn.execute(
            f"UPDATE crm_contacts SET {', '.join(fields)} WHERE id = ?",
            tuple(values),
        )
        row = conn.execute(
            (
                "SELECT id, full_name, email, phone, company, note, created_at, updated_at "
                "FROM crm_contacts WHERE id = ?"
            ),
            (contact_id,),
        ).fetchone()
    return row_to_dict(row)


@router.delete("/contacts/{contact_id}", status_code=200)
def delete_contact(contact_id: str) -> None:
    with get_connection() as conn:
        result = conn.execute("DELETE FROM crm_contacts WHERE id = ?", (contact_id,))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Contact not found")


@router.get("/deals", response_model=list[CRMDealOut])
def list_deals() -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            (
                "SELECT id, title, contact_id, status, value_amount, due_date, note, linked_task_id, "
                "created_at, updated_at FROM crm_deals ORDER BY created_at DESC"
            )
        ).fetchall()
    return [row_to_dict(row) for row in rows]


@router.post("/deals", response_model=CRMDealOut, status_code=201)
def create_deal(payload: CRMDealCreate) -> dict:
    deal_id = new_id()
    now = utc_now()

    with get_connection() as conn:
        if payload.contact_id is not None:
            contact_exists = conn.execute(
                "SELECT id FROM crm_contacts WHERE id = ?", (payload.contact_id,)
            ).fetchone()
            if contact_exists is None:
                raise HTTPException(status_code=400, detail="contact_id does not exist")

        if payload.linked_task_id is not None:
            task_exists = conn.execute(
                "SELECT id FROM tasks WHERE id = ?", (payload.linked_task_id,)
            ).fetchone()
            if task_exists is None:
                raise HTTPException(
                    status_code=400, detail="linked_task_id does not exist"
                )

        conn.execute(
            (
                "INSERT INTO crm_deals "
                "(id, title, contact_id, status, value_amount, due_date, note, linked_task_id, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            ),
            (
                deal_id,
                payload.title,
                payload.contact_id,
                payload.status,
                payload.value_amount,
                payload.due_date.isoformat() if payload.due_date else None,
                payload.note,
                payload.linked_task_id,
                now,
                now,
            ),
        )

        row = conn.execute(
            (
                "SELECT id, title, contact_id, status, value_amount, due_date, note, linked_task_id, "
                "created_at, updated_at FROM crm_deals WHERE id = ?"
            ),
            (deal_id,),
        ).fetchone()
    return row_to_dict(row)


@router.patch("/deals/{deal_id}", response_model=CRMDealOut)
def update_deal(deal_id: str, payload: CRMDealUpdate) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    with get_connection() as conn:
        exists = conn.execute(
            "SELECT id FROM crm_deals WHERE id = ?", (deal_id,)
        ).fetchone()
        if exists is None:
            raise HTTPException(status_code=404, detail="Deal not found")

        contact_id = updates.get("contact_id")
        if contact_id is not None:
            contact_exists = conn.execute(
                "SELECT id FROM crm_contacts WHERE id = ?", (contact_id,)
            ).fetchone()
            if contact_exists is None:
                raise HTTPException(status_code=400, detail="contact_id does not exist")

        linked_task_id = updates.get("linked_task_id")
        if linked_task_id is not None:
            task_exists = conn.execute(
                "SELECT id FROM tasks WHERE id = ?", (linked_task_id,)
            ).fetchone()
            if task_exists is None:
                raise HTTPException(
                    status_code=400, detail="linked_task_id does not exist"
                )

        fields: list[str] = []
        values: list[str | float | None] = []
        for key, value in updates.items():
            fields.append(f"{key} = ?")
            if hasattr(value, "isoformat") and value is not None:
                values.append(value.isoformat())
            else:
                values.append(value)

        fields.append("updated_at = ?")
        values.append(utc_now())
        values.append(deal_id)

        conn.execute(
            f"UPDATE crm_deals SET {', '.join(fields)} WHERE id = ?", tuple(values)
        )
        row = conn.execute(
            (
                "SELECT id, title, contact_id, status, value_amount, due_date, note, linked_task_id, "
                "created_at, updated_at FROM crm_deals WHERE id = ?"
            ),
            (deal_id,),
        ).fetchone()
    return row_to_dict(row)


@router.delete("/deals/{deal_id}", status_code=200)
def delete_deal(deal_id: str) -> None:
    with get_connection() as conn:
        result = conn.execute("DELETE FROM crm_deals WHERE id = ?", (deal_id,))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Deal not found")
