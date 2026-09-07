import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from './auth.service';

/** Requires any logged-in user. */
export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return auth.isLoggedIn ? true : router.createUrlTree(['/login']);
};

/** Requires the active organization role to be in the allowed list. */
export const roleGuard = (allowedRoles: string[]): CanActivateFn => () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (!auth.isLoggedIn) {
    return router.createUrlTree(['/login']);
  }
  return allowedRoles.includes(auth.role) ? true : router.createUrlTree(['/dashboard']);
};

/** The teaching dashboard has nothing to show a school owner, so anyone reaching it
 *  directly (bookmark, root redirect) is sent to the school dashboard instead.
 *  Principals and vice principals are sent to their leadership desk. */
export const ownerHomeGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  if (auth.isOwner && !auth.isIndividual) {
    return router.createUrlTree(['/admin/dashboard']);
  }
  if (auth.isLeadership) {
    return router.createUrlTree(['/leadership']);
  }
  return true;
};
