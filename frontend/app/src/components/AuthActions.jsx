// Topbar auth controls: Login/Register actions when signed out, chip + Sign out when in.
export default function AuthActions({ signedIn, onOpen, onSignOut }) {
  return (
    <div className="tb-auth">
      {signedIn ? (
        <>
          <span className="userchip" aria-label="You are signed in">● Signed in</span>
          <button type="button" className="btn small" onClick={onSignOut} aria-label="Sign out of Imad">
            Sign out
          </button>
        </>
      ) : (
        <>
          <button type="button" className="btn small" onClick={() => onOpen('login')} aria-label="Log in to Imad">
            Log in
          </button>
          <button type="button" className="btn primary small" onClick={() => onOpen('register')} aria-label="Create a free Imad account">
            Sign up
          </button>
        </>
      )}
    </div>
  )
}