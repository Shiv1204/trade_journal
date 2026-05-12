'use client';

import { Trade } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function TradeChart({ trades }: { trades: Trade[] }) {
  const sortedTrades = [...trades].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  let cumulative = 0;
  const data = sortedTrades.map(trade => {
    cumulative += trade.profit_loss || 0;
    return {
      date: trade.date,
      profit: cumulative,
    };
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profit/Loss Over Time</CardTitle>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip formatter={(value) => [`$${value}`, 'Cumulative P/L']} />
            <Line type="monotone" dataKey="profit" stroke="#8884d8" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}