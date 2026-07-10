import { renderAuthWall, type AuthWallHandlers } from './views/authWall'
import { renderAppView, type Affirmation, type AppViewProps } from './views/appView'

export interface MeResponse {
  username: string
  is_curator: boolean
}

export interface BootApi {
  getMe: () => Promise<MeResponse | null>
  getAffirmations: () => Promise<Affirmation[]>
}

// boot() is the pure, testable dispatch: given an injected api, decide
// whether to show the auth wall or the app view and append it into
// `container`. It deliberately knows nothing about login/register/logout
// networking -- BootApi only exposes read dispatch calls. The real browser
// entrypoint (src/entry.ts) wires actual interactive behavior on top of the
// DOM this renders.
export async function boot(container: HTMLElement, api: BootApi): Promise<void> {
  const me = await api.getMe()
  container.innerHTML = ''

  if (me === null) {
    const handlers: AuthWallHandlers = {
      onLogin: () => {},
      onRegister: () => {},
    }
    container.appendChild(renderAuthWall(handlers))
    return
  }

  const affirmations = await api.getAffirmations()
  const props: AppViewProps = {
    affirmations,
    isCurator: me.is_curator,
    onLogout: () => {},
  }
  container.appendChild(renderAppView(props))
}
