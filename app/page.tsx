'use client';

import { useState, useEffect } from 'react';
import TradeForm from '../components/TradeForm';
import TradeList from '../components/TradeList';
import TradeChart from '../components/TradeChart';
import { Trade } from '../types';
import { supabase } from '../lib/supabase';

export default function Home() {
  const [trades, setTrades] = useState<Trade[]>([]);

  useEffect(() => {
    fetchTrades();
  }, []);

  const fetchTrades = async () => {
    const { data, error } = await supabase.from('trades').select('*');
    if (error) {
      console.error('Error fetching trades:', error);
    } else {
      setTrades(data || []);
    }
  };

  const addTrade = async (trade: Trade) => {
    const { data, error } = await supabase.from('trades').insert([trade]).select();
    if (error) {
      console.error('Error adding trade:', error);
    } else {
      setTrades([...trades, ...data]);
    }
  };

  return (
    <main className="min-h-screen bg-background py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <h1 className="text-4xl font-bold text-center mb-8">Trade Journal</h1>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          <TradeForm onAddTrade={addTrade} />
          <TradeList trades={trades} />
        </div>
        <TradeChart trades={trades} />
      </div>
    </main>
  );
}