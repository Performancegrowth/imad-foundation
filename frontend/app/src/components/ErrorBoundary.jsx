import { Component } from 'react';

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    console.error('ErrorBoundary caught:', error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '60px 40px',
          color: '#fff',
          fontFamily: 'Inter, system-ui, sans-serif',
          background: '#020212',
          minHeight: '100vh',
        }}>
          <h1 style={{ fontSize: 32, fontWeight: 500, marginBottom: 16 }}>
            Something went wrong
          </h1>
          <p style={{ color: '#ffffff80', marginBottom: 24 }}>
            The page encountered an error. Try refreshing, or go back to the homepage.
          </p>
          <pre style={{
            background: '#030424',
            padding: 16,
            borderRadius: 4,
            fontSize: 12,
            color: '#ff2e79',
            overflow: 'auto',
            maxHeight: 300,
          }}>
            {String(this.state.error?.message || this.state.error)}
          </pre>
          <a href="/" style={{
            display: 'inline-block',
            marginTop: 24,
            padding: '10px 20px',
            background: '#fff',
            color: '#030424',
            borderRadius: 6,
            textDecoration: 'none',
            fontWeight: 500,
          }}>Go home</a>
        </div>
      );
    }
    return this.props.children;
  }
}
