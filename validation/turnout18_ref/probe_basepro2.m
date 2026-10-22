function probe_basepro2()
% Dig into BasePro.ND / NSET / ESET: which sets exist and what a node record holds.
root = 'G:\研究生\SDITT-RW-FT-250728\SDITT-RW-FT-250728';
old = cd(root);
cleanup = onCleanup(@() cd(old));
S = load(fullfile(root, 'BasePro.mat'));
B = S.BasePro;
f = fieldnames(B);
for i = 1:numel(f)
    v = B.(f{i});
    fprintf('-- %s: %s %s\n', f{i}, class(v), mat2str(size(v)));
    if isstruct(v) && numel(v) > 0
        fprintf('   fields: %s\n', strjoin(fieldnames(v)', ', '));
        g = fieldnames(v);
        for k = 1:numel(g)
            x = v(1).(g{k});
            if isnumeric(x)
                fprintf('   %s: %s  first %s\n', g{k}, class(x), mat2str(x(1:min(numel(x), 6)), 6));
            elseif ischar(x)
                fprintf('   %s: %s\n', g{k}, x);
            else
                fprintf('   %s: %s %s\n', g{k}, class(x), mat2str(size(x)));
            end
        end
    elseif iscell(v)
        fprintf('   cell, first: %s\n', class(v{1}));
        for k = 1:min(numel(v), 4)
            x = v{k};
            if ischar(x)
                fprintf('     [%d] %s\n', k, x);
            elseif isstruct(x) && numel(x) > 0
                fprintf('     [%d] struct fields: %s\n', k, strjoin(fieldnames(x)', ', '));
                fprintf('         first: %s\n', mat2str(x(1).location, 7));
            else
                fprintf('     [%d] %s %s\n', k, class(x), mat2str(size(x)));
            end
        end
    elseif isnumeric(v)
        fprintf('   first rows: %s\n', mat2str(v(1:min(3, size(v, 1)), 1:min(4, size(v, 2))), 7));
    end
end
end
