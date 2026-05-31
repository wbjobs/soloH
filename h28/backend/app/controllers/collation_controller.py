from typing import Optional, Tuple, Dict, Any, List
from app import db
from app.models.collation import Collation
from app.repositories.collation_repository import CollationRepository
from app.repositories.result_repository import ResultRepository
from app.services.collation_service import CollationService


class CollationController:
    def __init__(self):
        self.collation_repository = CollationRepository(db.session)
        self.result_repository = ResultRepository(db.session)
        self.collation_service = CollationService(
            self.collation_repository,
            self.result_repository
        )

    def _serialize(self, collation: Collation) -> Dict[str, Any]:
        return {
            'id': collation.id,
            'baseTaskId': collation.base_task_id,
            'comparedTaskId': collation.compared_task_id,
            'basePageNumber': collation.base_page_number,
            'comparedPageNumber': collation.compared_page_number,
            'alignmentScore': collation.alignment_score,
            'diffResult': collation.diff_result,
            'status': collation.status,
            'createdAt': collation.created_at.isoformat() if collation.created_at else None,
            'completedAt': collation.completed_at.isoformat() if collation.completed_at else None
        }

    def _serialize_list(self, collations: List[Collation]) -> List[Dict[str, Any]]:
        return [self._serialize(c) for c in collations]

    def create_collation(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
        try:
            base_task_id = data.get('baseTaskId')
            compared_task_id = data.get('comparedTaskId')
            base_page_number = data.get('basePageNumber')
            compared_page_number = data.get('comparedPageNumber')

            if not base_task_id or not compared_task_id or base_page_number is None:
                return {'error': 'Missing required fields'}, 400

            collation = self.collation_service.create_collation(
                base_task_id=base_task_id,
                compared_task_id=compared_task_id,
                base_page_number=base_page_number,
                compared_page_number=compared_page_number
            )

            return self._serialize(collation), 201
        except Exception as e:
            db.session.rollback()
            return {'error': str(e)}, 500

    def get_collation(self, collation_id: str) -> Tuple[Dict[str, Any], int]:
        try:
            collation = self.collation_service.get_collation(collation_id)
            if not collation:
                return {'error': 'Collation not found'}, 404
            return self._serialize(collation), 200
        except Exception as e:
            return {'error': str(e)}, 500

    def list_collations(self, task_id: str) -> Tuple[Dict[str, Any], int]:
        try:
            collations = self.collation_service.list_collations(task_id)
            return {
                'items': self._serialize_list(collations),
                'total': len(collations)
            }, 200
        except Exception as e:
            return {'error': str(e)}, 500
