export interface Trade {
  id: string;
  position: 'buy' | 'sell';
  date: string;
  entry_price: number;
  exit_price: number;
  stop_loss: number;
  quantity: number;
  profit_loss?: number;
}