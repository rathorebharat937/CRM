import { Link } from "react-router-dom";

function UserSignup() {
  return (
    <div className="crm-card">
      <h2>Portal signup closed</h2>
      <p className="crm-muted">
        Client portal accounts are created by your company admin. To run your own
        business on BlackPapers, register a new workspace instead.
      </p>
      <Link to="/register-company" className="crm-btn crm-btn-primary">
        Register your business
      </Link>
      <p className="crm-auth-switch crm-mt">
        <Link to="/user-login">Portal sign in</Link>
        {" · "}
        <Link to="/">Back to home</Link>
      </p>
    </div>
  );
}

export default UserSignup;
