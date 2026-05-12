import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error(
    'Missing Supabase environment variables. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY in .env.local.'
  )
}

if (!/^https?:\/\//.test(supabaseUrl)) {
  throw new Error('Invalid Supabase URL. NEXT_PUBLIC_SUPABASE_URL must be a valid HTTP or HTTPS URL.')
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)