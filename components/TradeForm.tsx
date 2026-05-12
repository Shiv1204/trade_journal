'use client';

import { useState } from 'react';
import { Trade } from '../types';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function TradeForm({ onAddTrade }: { onAddTrade: (trade: Trade) => void }) {
  const [position, setPosition] = useState<'buy' | 'sell'>('buy');
  const [date, setDate] = useState('');
  const [entryPrice, setEntryPrice] = useState('');
  const [exitPrice, setExitPrice] = useState('');
  const [stopLoss, setStopLoss] = useState('');
  const [quantity, setQuantity] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trade: Trade = {
      id: Date.now().toString(),
      position,
      date,
      entry_price: parseFloat(entryPrice),
      exit_price: parseFloat(exitPrice),
      stop_loss: parseFloat(stopLoss),
      quantity: parseInt(quantity),
    };
    trade.profit_loss = calculateProfitLoss(trade);
    onAddTrade(trade);
    // Reset form
    setDate('');
    setEntryPrice('');
    setExitPrice('');
    setStopLoss('');
    setQuantity('');
  };

  const calculateProfitLoss = (trade: Trade) => {
    const { position, entry_price, exit_price, quantity } = trade;
    if (position === 'buy') {
      return (exit_price - entry_price) * quantity;
    } else {
      return (entry_price - exit_price) * quantity;
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Add New Trade</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Position</label>
              <Select value={position} onValueChange={(value: 'buy' | 'sell') => setPosition(value)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="buy">Buy</SelectItem>
                  <SelectItem value="sell">Sell</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Date</label>
              <Input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Entry Price</label>
              <Input
                type="number"
                step="0.01"
                value={entryPrice}
                onChange={(e) => setEntryPrice(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Exit Price</label>
              <Input
                type="number"
                step="0.01"
                value={exitPrice}
                onChange={(e) => setExitPrice(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Stop Loss</label>
              <Input
                type="number"
                step="0.01"
                value={stopLoss}
                onChange={(e) => setStopLoss(e.target.value)}
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Quantity</label>
              <Input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                required
              />
            </div>
          </div>
          <Button type="submit" className="w-full">Add Trade</Button>
        </form>
      </CardContent>
    </Card>
  );
}