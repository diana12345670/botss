from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class Bet:
    """Representa uma aposta ativa"""
    bet_id: str
    mode: str
    player1_id: int
    player2_id: int
    mediator_id: int
    channel_id: int
    team1_ids: List[int] = None
    team2_ids: List[int] = None
    bet_value: float = 0.0
    mediator_fee: float = 0.0
    mediator_pix: Optional[str] = None
    player1_confirmed: bool = False
    player2_confirmed: bool = False
    team1_confirmed: bool = False
    team2_confirmed: bool = False
    winner_id: Optional[int] = None
    winner_team: Optional[int] = None
    created_at: str = ""
    finished_at: Optional[str] = None
    currency_type: str = "sonhos"

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

        if self.team1_ids is None:
            self.team1_ids = []
        if self.team2_ids is None:
            self.team2_ids = []

    def is_fully_confirmed(self) -> bool:
        """Verifica se ambos os jogadores confirmaram pagamento"""
        if self.mode.startswith("2v2"):
            return self.team1_confirmed and self.team2_confirmed
        return self.player1_confirmed and self.player2_confirmed

    def to_dict(self) -> dict:
        """Converte a aposta para dicionário"""
        return {
            'bet_id': self.bet_id,
            'mode': self.mode,
            'player1_id': self.player1_id,
            'player2_id': self.player2_id,
            'team1_ids': self.team1_ids,
            'team2_ids': self.team2_ids,
            'mediator_id': self.mediator_id,
            'channel_id': self.channel_id,
            'bet_value': self.bet_value,
            'mediator_fee': self.mediator_fee,
            'mediator_pix': self.mediator_pix,
            'player1_confirmed': self.player1_confirmed,
            'player2_confirmed': self.player2_confirmed,
            'team1_confirmed': self.team1_confirmed,
            'team2_confirmed': self.team2_confirmed,
            'winner_id': self.winner_id,
            'winner_team': self.winner_team,
            'created_at': self.created_at,
            'finished_at': self.finished_at,
            'currency_type': self.currency_type
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Bet':
        """Cria uma aposta a partir de um dicionário"""
        return cls(
            bet_id=data['bet_id'],
            mode=data['mode'],
            player1_id=data['player1_id'],
            player2_id=data['player2_id'],
            team1_ids=data.get('team1_ids', []) or [],
            team2_ids=data.get('team2_ids', []) or [],
            mediator_id=data['mediator_id'],
            channel_id=data['channel_id'],
            bet_value=data['bet_value'],
            mediator_fee=data['mediator_fee'],
            mediator_pix=data.get('mediator_pix', None),
            player1_confirmed=data.get('player1_confirmed', False),
            player2_confirmed=data.get('player2_confirmed', False),
            team1_confirmed=data.get('team1_confirmed', False),
            team2_confirmed=data.get('team2_confirmed', False),
            winner_id=data.get('winner_id', None),
            winner_team=data.get('winner_team', None),
            created_at=data.get('created_at', ''),
            finished_at=data.get('finished_at', None),
            currency_type=data.get('currency_type', 'sonhos')
        )