import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('ClaimGuard UI', () => {
  it('muestra el formulario de auditoría inicial', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Datos de la factura' })).toBeTruthy()
    expect(screen.getByRole('button', { name: /Iniciar auditoría/i })).toBeTruthy()
  })
})
