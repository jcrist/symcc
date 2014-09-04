# Symcc - Symbolic Math Compiler

An experimental code printing, generation, wrapping, and compilation library
for SymPy.

Much of the code is pulled from the SymPy code base, with intent to merge all
(or at least most) of the added features after they've been thoroughly tested
and developed.

## Planned Features

- Template support
- Improved broadcasting and looping support
- Module level intent definition
- Optimizing transformations
- Common subexpression elimination
- Inclusion of C/Fortran libraries for uncommon functions
- Matrix operations
- Improved extesibility/modularity of printers, generators, and wrappers
- Pipelinable operations

## Why?

After fixing a bunch of issues on code printing, generation, and wrapping
in SymPy proper, I came to the realization that these features need a fairly
substantial redesign to get them to a point where they're truly usable. As this
will require major changes to the codebase, I've pulled the relevent files into
this separate library. The intent is for the new features to be added and tested
here, and then eventually merged back into SymPy proper as a top-level module.

I don't expect everything added to make the cut (Templating engines probably
won't), but ideally most of the changes will eventually find their way back
into SymPy.
