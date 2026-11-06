import React, { useState, useEffect } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import {
  Shield,
  LayoutDashboard,
  FilePlus2,
  Map,
  LogOut,
  Menu,
  X,
  Settings,
  Bell,
  ChevronRight,
  Activity,
  UserRound,
} from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { useLang } from '../i18n'

// ── Nav Item Definition ───────────────────────────────────────
interface NavItem {
  label: string
  href: string
  icon: React.ElementType
  roles?: Array<'citizen' | 'officer' | 'admin'>
  badge?: string
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Citizen Portal', href: '/dashboard', icon: LayoutDashboard, roles: ['citizen', 'admin'] },
  { label: 'Report Issue',  href: '/report',    icon: FilePlus2,       roles: ['citizen'] },
  { label: 'Officer Queue', href: '/officer',   icon: Activity,        roles: ['officer'] },
  { label: 'Admin Panel',   href: '/admin',     icon: Settings,        roles: ['admin'] },
  { label: 'GIS Analytics', href: '/analytics', icon: Map,             roles: ['citizen', 'officer', 'admin'] },
]

type UserRole = 'citizen' | 'officer' | 'admin'

// ── Sidebar Component ─────────────────────────────────────────
interface SidebarProps {
  isOpen: boolean
  onClose: () => void
}

const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const userRole = (user?.role || 'citizen') as UserRole

  const visibleItems = NAV_ITEMS.filter((item) =>
    !item.roles || item.roles.includes(userRole)
  )

  const handleLogout = () => {
    logout()
    navigate('/login')
    onClose()
  }

  // Close sidebar on route change on mobile
  useEffect(() => {
    onClose()
  }, [location.pathname]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      {/* Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-40 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Sidebar panel */}
      <nav
        className={`sidebar ${isOpen ? 'open' : ''}`}
        aria-label="Main navigation"
        role="navigation"
      >
        {/* Brand */}
        <div className="flex items-center gap-3 px-4 py-5 border-b border-white/10">
          <div className="w-8 h-8 rounded-lg bg-white/15 flex items-center justify-center shrink-0" aria-hidden="true">
            <Shield size={18} className="text-white" />
          </div>
          <div>
            <div className="text-white font-bold text-[1.0625rem] leading-tight">Namma Civic 2.0</div>
            <div className="text-white/50 text-[0.6875rem] font-mono uppercase tracking-wider mt-0.5">Bengaluru</div>
          </div>
          {/* Close on mobile */}
          <button
            onClick={onClose}
            aria-label="Close navigation"
            className="ml-auto icon-btn text-white/60 hover:text-white hover:bg-white/10 lg:hidden"
          >
            <X size={18} aria-hidden="true" />
          </button>
        </div>

        {/* Nav Links */}
        <div className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
          <p className="section-label px-2 mb-3 text-white/30">Navigation</p>
          {visibleItems.map((item) => {
            const Icon = item.icon
            const isActive = location.pathname === item.href ||
              (item.href !== '/' && location.pathname.startsWith(item.href))
            return (
              <Link
                key={item.href}
                to={item.href}
                className={`nav-link ${isActive ? 'active' : ''}`}
                aria-current={isActive ? 'page' : undefined}
              >
                <Icon size={18} aria-hidden="true" />
                <span className="flex-1">{item.label}</span>
                {item.badge && (
                  <span className="text-xs font-bold bg-red-500 text-white px-1.5 py-0.5 rounded-full font-mono">
                    {item.badge}
                  </span>
                )}
                {isActive && <ChevronRight size={14} className="opacity-60" aria-hidden="true" />}
              </Link>
            )
          })}
        </div>

        {/* User section */}
        {user && (
          <div className="p-3 border-t border-white/10 shrink-0">
            <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-white/10 mb-2">
              {/* Avatar */}
              <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center text-white font-bold text-sm shrink-0" aria-hidden="true">
                {(user.full_name || user.email)[0].toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-white text-sm font-semibold truncate">{user.full_name}</div>
                <div className="text-white/50 text-xs font-mono capitalize">{user.role}</div>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="nav-link w-full text-left"
              aria-label="Sign out of Namma Civic"
            >
              <LogOut size={16} aria-hidden="true" />
              Sign Out
            </button>
          </div>
        )}
      </nav>
    </>
  )
}

// ── Top Bar (Mobile) ──────────────────────────────────────────
interface TopBarProps {
  onMenuOpen: () => void
  title?: string
}

const TopBar: React.FC<TopBarProps> = ({ onMenuOpen, title }) => {
  const { user } = useAuthStore()
  const location = useLocation()

  // Derive page title from route
  const pageTitle = title || NAV_ITEMS.find(
    (n) => location.pathname === n.href || (n.href !== '/' && location.pathname.startsWith(n.href))
  )?.label || 'Namma Civic'

  return (
    <header className="topbar" role="banner">
      <button
        id="menu-open-btn"
        onClick={onMenuOpen}
        aria-label="Open navigation menu"
        aria-expanded={false}
        className="icon-btn shrink-0"
        style={{ color: '#fff' }}
      >
        <Menu size={22} aria-hidden="true" />
      </button>

      <div className="flex items-center gap-2 min-w-0 flex-1">
        <Shield size={20} className="shrink-0" style={{ color: '#F6C445' }} aria-hidden="true" />
        <span className="font-bold text-white truncate">{pageTitle}</span>
      </div>

      {user && (
        <div className="flex items-center gap-1 shrink-0">
          <button
            aria-label="Notifications"
            className="icon-btn"
            style={{ color: '#fff' }}
          >
            <Bell size={20} aria-hidden="true" />
          </button>
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold shrink-0"
            style={{ background: '#F6C445', color: '#5C1020' }}
            aria-label={`Logged in as ${user.full_name}`}
          >
            {(user.full_name || user.email)[0].toUpperCase()}
          </div>
        </div>
      )}
    </header>
  )
}

// ── Bottom Navigation (Mobile) ────────────────────────────────
const BottomNav: React.FC = () => {
  const location = useLocation()
  const { user } = useAuthStore()
  const userRole = (user?.role || 'citizen') as UserRole

  const items = NAV_ITEMS.filter((item) =>
    !item.roles || item.roles.includes(userRole)
  )

  return (
    <nav className="bottom-nav" role="navigation" aria-label="Mobile navigation">
      {items.map((item) => {
        const Icon = item.icon
        const isActive = location.pathname === item.href ||
          (item.href !== '/' && location.pathname.startsWith(item.href))
        return (
          <Link
            key={item.href}
            to={item.href}
            className={`bottom-link ${isActive ? 'active' : ''}`}
            aria-current={isActive ? 'page' : undefined}
            aria-label={item.label}
          >
            <Icon size={22} aria-hidden="true" />
            <span>{item.label.split(' ')[0]}</span>
          </Link>
        )
      })}
    </nav>
  )
}

// ── AppShell ──────────────────────────────────────────────────
interface AppShellProps {
  children: React.ReactNode
}

export const AppShell: React.FC<AppShellProps> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Trap focus when sidebar open on mobile
  useEffect(() => {
    if (sidebarOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => { document.body.style.overflow = '' }
  }, [sidebarOpen])

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Mobile top bar */}
      <TopBar onMenuOpen={() => setSidebarOpen(true)} />

      {/* Main content */}
      <main className="app-main" id="main-content">
        <div className="app-content">
          {children}
        </div>
      </main>

      {/* Mobile bottom nav */}
      <BottomNav />
    </div>
  )
}

// ── Public Page Wrapper (landing, login, register) ─────────────
interface PublicShellProps {
  children: React.ReactNode
}

export const PublicShell: React.FC<PublicShellProps> = ({ children }) => {
  const { isAuthenticated, user } = useAuthStore()
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const { lang, setLang, t } = useLang()

  const links = [
    { label: t('home'), href: '/' },
    { label: t('services'), href: '/services' },
    { label: t('track'), href: '/track' },
    { label: t('insights'), href: '/insights' },
  ]

  const initial = (user?.full_name || user?.email || 'N')[0].toUpperCase()
  const homeHref = user?.role === 'admin' ? '/admin' : user?.role === 'officer' ? '/officer' : '/dashboard'

  return (
    <div className="min-h-dvh flex flex-col" style={{ background: '#FFF6EA' }}>
      <header className="nc-top" role="banner">
        <div className="nc-top-inner">
          <Link to="/" className="nc-brand" aria-label="Namma Civic 2.0 home">
            <span className="nc-emblem" aria-hidden="true">
              <Shield size={20} />
            </span>
            <span className="nc-brand-text">
              <span className="nc-brand-kn">{t('brandKn')}</span>
              <span className="nc-brand-en">{t('brandEn')}</span>
              <span className="nc-brand-sub">{t('brandSub')}</span>
            </span>
          </Link>

          <nav className="nc-nav" aria-label="Public navigation">
            {links.map((l) => {
              const active = location.pathname === l.href
              return (
                <Link key={l.href} to={l.href} className={active ? 'active' : undefined} aria-current={active ? 'page' : undefined}>
                  {l.label}
                </Link>
              )
            })}
          </nav>

          <div className="nc-tools">
            <div className="nc-lang" role="group" aria-label="Language">
              <button type="button" className={lang === 'en' ? 'on' : undefined} onClick={() => setLang('en')}>EN</button>
              <button type="button" className={lang === 'kn' ? 'on' : undefined} onClick={() => setLang('kn')}>ಕನ್ನಡ</button>
            </div>
            <Link
              to={isAuthenticated ? homeHref : '/login'}
              className="nc-account"
              aria-label={isAuthenticated ? 'Open my requests' : t('signIn')}
            >
              {isAuthenticated ? initial : <UserRound size={16} />}
            </Link>
          </div>

          <button
            className="nc-menu-btn"
            onClick={() => setMobileMenuOpen((v) => !v)}
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileMenuOpen}
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>

        {mobileMenuOpen && (
          <nav className="nc-mobile-nav" aria-label="Mobile navigation">
            {links.map((l) => (
              <Link
                key={l.href}
                to={l.href}
                className={location.pathname === l.href ? 'active' : undefined}
                onClick={() => setMobileMenuOpen(false)}
              >
                {l.label}
              </Link>
            ))}
            <Link to="/departments" onClick={() => setMobileMenuOpen(false)}>{t('departments')}</Link>
            <Link to="/agents" onClick={() => setMobileMenuOpen(false)}>{t('agents')}</Link>
            <Link to={isAuthenticated ? homeHref : '/login'} onClick={() => setMobileMenuOpen(false)}>
              {isAuthenticated ? t('myRequests') : t('signIn')}
            </Link>
          </nav>
        )}
      </header>

      <div className="flex-1">{children}</div>

      <footer className="nc-footer" role="contentinfo">
        <div className="nc-footer-inner">
          <p>{t('footer')}</p>
          <div style={{ display: 'flex', gap: 16 }}>
            <Link to="/services">{t('services')}</Link>
            <Link to="/track">{t('track')}</Link>
            <Link to={isAuthenticated ? homeHref : '/register'}>
              {isAuthenticated ? t('myRequests') : t('signIn')}
            </Link>
          </div>
        </div>
      </footer>
    </div>
  )
}

// ── Protected Route ───────────────────────────────────────────
import { Navigate } from 'react-router-dom'

interface ProtectedRouteProps {
  children: React.ReactNode
  roles?: Array<'citizen' | 'officer' | 'admin'>
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, roles }) => {
  const { isAuthenticated, user } = useAuthStore()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (roles && user && !roles.includes(user.role as UserRole)) {
    return <Navigate to="/dashboard" replace />
  }

  return <>{children}</>
}

