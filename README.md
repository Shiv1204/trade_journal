# Trade Journal

A Next.js application to track your trades.

## Tech Stack

- React + TypeScript
- Tailwind CSS
- Shadcn UI
- Recharts for charts
- Supabase for backend

## Getting Started

First, install dependencies:

```bash
npm install
```

### Supabase Setup

1. Create a new project on [Supabase](https://supabase.com).
2. Go to Settings > API to get your project URL and anon key.
3. Create a `.env.local` file in the root directory and add:

```
NEXT_PUBLIC_SUPABASE_URL=your-project-url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key
```

4. Create a table called `trades` with the following schema:

```sql
CREATE TABLE trades (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  position TEXT NOT NULL,
  date DATE NOT NULL,
  entry_price DECIMAL NOT NULL,
  exit_price DECIMAL NOT NULL,
  stop_loss DECIMAL NOT NULL,
  quantity INTEGER NOT NULL,
  profit_loss DECIMAL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

Then, run the development server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Features

- Track positions, entry/exit prices, stop loss, and quantity
- Calculate profit/loss automatically
- View trade history in a table
- Visualize profit/loss over time with charts
- Data persisted in Supabase