import numpy as np
from scipy.optimize import curve_fit

def double_sigmoid(x, C, A, k, x0, d):
    """
    Constant plus one rising sigmoid at x0 and one falling sigmoid at x0+d.
    """
    s1 = A / (1 + np.exp(-k * (x - x0)))
    s2 = A / (1 + np.exp(-k * (x - (x0 + d))))
    return C + s1 - s2

def fit_double_sigmoid(x, y, d_guess, initial_guess=None, bounds=None):
    """
    Fit y(x) to a constant + two sigmoids (fixed center separation d),
    and return fit parameters, error, AND the fitted y-array.
    
    Parameters
    ----------
    x : array‐like of shape (N,)
        Independent variable.
    y : array‐like of shape (N,)
        Dependent data.
    d : float
        Fixed distance between the two sigmoid centers.
    initial_guess : sequence of 4 floats, optional
        [C, A, k, x0]. If None, guessed automatically.
    bounds : (2,4) tuple of array‐likes, optional
        Lower/upper bounds for (C, A, k, x0). If None, no bounds.
    
    Returns
    -------
    params : dict
        {'C':…, 'A':…, 'k':…, 'x0':…, 'x0_2':…}
    rmse : float
        Root‐mean‐square error of the fit.
    y_fit : ndarray of shape (N,)
        Model evaluated at each x with the best‐fit params.
    popt : ndarray of shape (4,)
        Raw optimized parameters [C, A, k, x0].
    pcov : ndarray of shape (4,4)
        Covariance matrix from curve_fit.
    """
    x = np.asarray(x)
    y = np.asarray(y)

    # wrapper holding d fixed
    def model(x, C, A, k, x0, d):
        return double_sigmoid(x, C, A, k, x0, d)

    # auto‐guess if needed
    if initial_guess is None:
        C0 = np.min(y)
        A0 = (np.max(y) - np.min(y)) / 2
        k0 = 1.0 
        x0_0 = x[np.argmax(y)]-(d_guess/2)
        d0 = d_guess
        initial_guess = [C0, A0, k0, x0_0, d0]
        print(initial_guess)

    if bounds is None:
        bounds = (-np.inf, np.inf)

    # fit
    try:
        popt, pcov = curve_fit(
            model, x, y,
            p0=initial_guess,
            bounds=bounds,
            maxfev=5000      # you can include this too
        )
    except RuntimeError as e:
        print(f"[fit_double_sigmoid] fit did not converge: {e}")
        # return a flag or defaults so caller can skip this point
        return None, None, None, None, None, None

    # build the fitted curve
    y_fit = model(x, *popt)

    # compute RMSE
    rmse = np.sqrt(np.mean((y - y_fit) ** 2))

    params = {
        'C':    popt[0],
        'A':    popt[1],
        'k':    popt[2],
        'x0':   popt[3],
        'x0_2': popt[3] + popt[4],
    }
    print("done fitting")
    #print(y_fit)
    return params, rmse, y_fit, popt, pcov, popt[3]+(popt[4]/2)
