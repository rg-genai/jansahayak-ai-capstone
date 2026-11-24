import React from 'react'
import { CloudShader } from './ui/cloud-shader'
import { useTheme } from '../hooks/useTheme'

const LIGHT_PALETTE = {
  skyTopColor: '#3876ba',
  skyBottomColor: '#8cbfe8',
  cloudColor: '#fbf8f2',
}

const DARK_PALETTE = {
  skyTopColor: '#0b1f36',
  skyBottomColor: '#1d3f63',
  cloudColor: '#8a94a3',
}

export const AppBackground: React.FC = () => {
  const { theme } = useTheme()
  const palette = theme === 'dark' ? DARK_PALETTE : LIGHT_PALETTE

  return (
    <div className="fixed inset-0 -z-10" aria-hidden="true">
      <CloudShader className="h-full w-full" {...palette} />
    </div>
  )
}
