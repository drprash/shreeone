from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from app import schemas, models, crud, auth
from app.database import get_db

router = APIRouter(prefix="/categories", tags=["Categories"])

@router.put("/reorder", status_code=200)
def reorder_categories(
    items: List[schemas.CategoryReorderItem],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    crud.reorder_categories(db, current_user.family_id, items)
    return {"status": "ok"}

@router.post("/", response_model=schemas.CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    category: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # Only admin can create family-wide categories
    if current_user.role != models.Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can create categories"
        )
    
    return crud.create_category(db, category, current_user.family_id)

@router.get("/", response_model=List[schemas.CategoryResponse])
def list_categories(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    return crud.get_family_categories(db, current_user.family_id)

@router.put("/{category_id}", response_model=schemas.CategoryResponse)
def update_category(
    category_id: UUID,
    category_update: schemas.CategoryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    category = crud.get_category(db, category_id)
    if not category or category.family_id != current_user.family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    for field, value in category_update.dict().items():
        setattr(category, field, value)
    
    db.commit()
    db.refresh(category)
    return category

@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_admin)
):
    category = crud.get_category(db, category_id)
    if not category or category.family_id != current_user.family_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    if not crud.delete_category(db, category_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found"
        )
    
    return None
