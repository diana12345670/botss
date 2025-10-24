from dataclasses import dataclass
from typing import Optional
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
    bet_value: float = 0.0
    mediator_fee: float = 0.0
    mediator_pix: Optional[str] = None
    player1_confirmed: bool = False
    player2_confirmed: bool = False
    winner_id: Optional[int] = None
    created_at: str = ""
    finished_at: Optional[str] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def is_fully_confirmed(self) -> bool:
        """Verifica se ambos os jogadores confirmaram pagamento"""
        return self.player1_confirmed and self.player2_confirmed
    
    def to_dict(self) -> dict:
        """Converte a aposta para dicionário"""
        return {
            'bet_id': self.bet_id,
            'mode': self.mode,
            'player1_id': self.player1_id,
            'player2_id': self.player2_id,
            'mediator_id': self.mediator_id,
            'channel_id': self.channel_id,
            'bet_value': self.bet_value,
            'mediator_fee': self.mediator_fee,
            'mediator_pix': self.mediator_pix,
            'player1_confirmed': self.player1_confirmed,
            'player2_confirmed': self.player2_confirmed,
            'winner_id': self.winner_id,
            'created_at': self.created_at,
            'finished_at': self.finished_at
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Bet':
        """Cria uma aposta a partir de um dicionário"""
        return cls(**data)
