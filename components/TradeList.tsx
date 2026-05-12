'use client';

import { Trade } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export default function TradeList({ trades }: { trades: Trade[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Trade History</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Position</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Entry</TableHead>
              <TableHead>Exit</TableHead>
              <TableHead>SL</TableHead>
              <TableHead>Qty</TableHead>
              <TableHead>P/L</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {trades.map((trade) => (
              <TableRow key={trade.id}>
                <TableCell className="font-medium">{trade.position.toUpperCase()}</TableCell>
                <TableCell>{trade.date}</TableCell>
              <TableCell>${trade.entry_price.toFixed(2)}</TableCell>
              <TableCell>${trade.exit_price.toFixed(2)}</TableCell>
              <TableCell>${trade.stop_loss.toFixed(2)}</TableCell>
              <TableCell>{trade.quantity}</TableCell>
              <TableCell className={trade.profit_loss && trade.profit_loss >= 0 ? 'text-green-600' : 'text-red-600'}>
                ${trade.profit_loss?.toFixed(2)}
              </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}