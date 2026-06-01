import { Routes, Route } from 'react-router-dom'
import Navbar from './components/layout/Navbar'
import Footer from './components/layout/Footer'
import LandingPage from './pages/LandingPage'
import ReportPage from './pages/ReportPage'
import DashboardPage from './pages/DashboardPage'
import ComparePage from './pages/ComparePage'
import AlertsPage from './pages/AlertsPage'
import DiscoveryPage from './pages/DiscoveryPage'
import NotFoundPage from './pages/NotFoundPage'
import { ThemeProvider } from './contexts/ThemeContext'

export default function App() {
  return (
    <ThemeProvider>
      <div className="min-h-screen flex flex-col">
        <Navbar />
        <main className="flex-1 pt-16 print:pt-0">
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/report/:ticker" element={<ReportPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/discover" element={<DiscoveryPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </main>
        <Footer />
      </div>
    </ThemeProvider>
  )
}
