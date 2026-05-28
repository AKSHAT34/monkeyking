import './globals.css';
import { Inter } from 'next/font/google';
import { Providers } from '@/providers/Providers';

const inter = Inter({ subsets: ['latin'] });

export const metadata = {
  title: '🐵 MonkeyKing — Help You Climb Your Career Ladder',
  description: 'AI-powered job search platform that helps you climb your career ladder',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.className}>
      <body className="min-h-screen bg-mk-dark text-white">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
