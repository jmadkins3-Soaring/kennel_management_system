import NavBar from './NavBar'

export default function Layout({ children }) {
  return (
    <>
      <NavBar />
      <div style={{ marginTop: 'var(--nav-h)' }}>
        {children}
      </div>
    </>
  )
}
