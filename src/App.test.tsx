import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App'

describe('ClaimGuard UI', () => {
  it('muestra el formulario de auditoría inicial', () => {
    render(<App />)
    expect(screen.getByText('Hola, soy ClaimGuard.')).toBeTruthy()
    expect(screen.getByRole('button', { name: /Enviar/i })).toBeTruthy()
  })
})
